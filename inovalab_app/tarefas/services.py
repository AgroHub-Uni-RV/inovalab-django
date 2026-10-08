import sqlite3
from functools import wraps
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.agenda.models import AgendaServico
from inovalab_app.tarefas.models import EventoTarefa, StatusTarefa, Tarefa
from inovalab_app.tarefas.selectors import visible_tasks
from inovalab_app.tarefas.links import (
    LINK_FIELDS, LEGACY_LINK_FIELDS, apply_legacy_aliases, link_snapshot,
    lock_and_validate_links, normalize_links, persist_links,
)


PUBLIC_FIELDS = {'agendamento_servico', 'descricao'} | LINK_FIELDS | LEGACY_LINK_FIELDS
TRACKED_FIELDS = (*sorted(PUBLIC_FIELDS - LINK_FIELDS), 'status', 'inicio', 'conclusao', 'excluida_em')
TRANSITIONS = {
    'iniciar': ('demanda', 'criacao'),
    'enviar': ('criacao', 'avaliacao'),
    'aprovar': ('avaliacao', 'concluido'),
    'recusar': ('avaliacao', 'criacao'),
    'reabrir': ('concluido', 'criacao'),
}
ADMIN_ACTIONS = {'aprovar', 'recusar', 'reabrir'}


class TaskConflict(Exception):
    """The task changed since the caller read it."""


def _require_active(actor):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied('É necessária uma conta interna ativa.')


def _require_admin(actor):
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem executar esta ação.')


def _load(actor, task_id, expected_version):
    _require_active(actor)
    task = get_object_or_404(visible_tasks(actor), pk=task_id)
    if type(expected_version) is not int or expected_version < 1:
        raise ValidationError({'versao': 'Informe a versão inteira positiva da tarefa.'})
    if task.versao != expected_version:
        raise TaskConflict('A tarefa foi alterada. Atualize a página antes de tentar novamente.')
    return task


def _snapshot(task):
    values = {}
    for name in TRACKED_FIELDS:
        value = getattr(task, task._meta.get_field(name).attname)
        values[name] = value.isoformat() if isinstance(value, datetime) else value
    return {**values, **link_snapshot(task)}


def _record(actor, task, action, before):
    after = _snapshot(task)
    changes = {key: {'anterior': before.get(key), 'novo': value}
               for key, value in after.items() if before.get(key) != value}
    EventoTarefa.objects.create(
        tarefa=task, ator=actor, ator_nome=actor.username, acao=action,
        status_anterior=before.get('status', ''), status_novo=task.status, alteracoes=changes,
    )


@transaction.atomic
def _persist(actor, task, action, before, expected_version, links=None):
    # A conditional UPDATE provides version protection on SQLite too.
    values = {name: getattr(task, task._meta.get_field(name).attname) for name in TRACKED_FIELDS}
    values['versao'] = expected_version + 1
    changed = Tarefa.objects.filter(pk=task.pk, versao=expected_version, excluida_em__isnull=True).update(**values)
    if not changed:
        raise TaskConflict('A tarefa foi alterada. Atualize a página antes de tentar novamente.')
    task.versao = expected_version + 1
    if links is not None:
        persist_links(task, links)
    _record(actor, task, action, before)
    return task


def allowed_actions(actor, task):
    if not actor.is_authenticated or not actor.is_active or task.excluida_em:
        return []
    admin = is_business_admin(actor)
    if not admin and not task.responsaveis.filter(pk=actor.pk).exists():
        return []
    return [action for action, (source, _) in TRANSITIONS.items()
            if source == task.status and (admin or action not in ADMIN_ACTIONS)]


def _busy_as_task_conflict(operation):
    @wraps(operation)
    def wrapped(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except OperationalError as error:
            code = getattr(error.__cause__, 'sqlite_errorcode', 0)
            if connection.vendor == 'sqlite' and (code & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise TaskConflict('Os registros estão sendo alterados. Atualize e tente novamente.') from error
            raise
    return wrapped


def _lock_references(task):
    # Use the same service-row lock as approval/cancellation. No-op writes also
    # acquire the SQLite write lock before validation reads (select_for_update does not).
    from inovalab_app.agenda.services import _lock_targets
    if task.agendamento_servico_id is not None:
        _lock_targets(('servico', task.agendamento_servico.servico_id))


@_busy_as_task_conflict
def save_task(*, actor, data, task_id=None, expected_version=None):
    _require_active(actor)
    task = _load(actor, task_id, expected_version) if task_id is not None else Tarefa()
    _require_admin(actor)
    unknown = set(data) - PUBLIC_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    before = _snapshot(task) if task_id is not None else {}
    links = normalize_links(task, data)
    for name in ('agendamento_servico', 'descricao'):
        if name not in data:
            continue
        value = data[name]
        if name == 'agendamento_servico' and (not isinstance(value, AgendaServico) or value.pk is None):
            raise ValidationError({name: 'Selecione um cadastro válido.'})
        setattr(task, name, value)
    apply_legacy_aliases(task, links, data)
    with transaction.atomic():
        _lock_references(task)
        if task.agendamento_servico_id is not None and task.agendamento_servico_id != before.get('agendamento_servico'):
            if not AgendaServico.objects.filter(pk=task.agendamento_servico_id, situacao='confirmado', cancelado_em__isnull=True).exists():
                raise ValidationError({'agendamento_servico': 'Selecione um agendamento confirmado e não cancelado.'})
        lock_and_validate_links(links, before)
        task.full_clean()
        if task_id is None:
            task.save()
            persist_links(task, links)
            _record(actor, task, 'criar', before)
            return task
        return _persist(actor, task, 'editar', before, expected_version, links=links)


def transition_task(*, actor, task_id, action, expected_version):
    task = _load(actor, task_id, expected_version)
    if action in ADMIN_ACTIONS:
        _require_admin(actor)
    if action not in allowed_actions(actor, task):
        raise ValidationError({'acao': 'Esta transição não é válida no estado atual.'})
    before = _snapshot(task)
    task.status = TRANSITIONS[action][1]
    if action == 'iniciar':
        task.inicio = timezone.now()
    elif action == 'aprovar':
        task.conclusao = timezone.now()
    elif action == 'reabrir':
        task.conclusao = None
    task.full_clean()
    return _persist(actor, task, action, before, expected_version)


def delete_task(*, actor, task_id, expected_version):
    task = _load(actor, task_id, expected_version)
    _require_admin(actor)
    before = _snapshot(task)
    task.excluida_em = timezone.now()
    return _persist(actor, task, 'excluir', before, expected_version)


def allowed_statuses(actor, task):
    if actor.is_authenticated and actor.is_active and not task.excluida_em and is_business_admin(actor):
        return StatusTarefa.values
    return [task.status, *dict.fromkeys(TRANSITIONS[action][1] for action in allowed_actions(actor, task))]


def set_task_status(*, actor, task_id, status, expected_version):
    task = _load(actor, task_id, expected_version)
    if not is_business_admin(actor) and not task.responsaveis.filter(pk=actor.pk).exists():
        raise PermissionDenied('Esta tarefa pertence a outro responsável.')
    if status == task.status:
        return task
    if is_business_admin(actor):
        if status not in StatusTarefa.values:
            raise ValidationError({'status': 'Selecione um status válido.'})
        actions = [action for action in allowed_actions(actor, task) if TRANSITIONS[action][1] == status]
        if actions:
            return transition_task(actor=actor, task_id=task_id, action=actions[0], expected_version=expected_version)
        before = _snapshot(task)
        task.status = status
        now = timezone.now()
        if status != StatusTarefa.DEMANDA and task.inicio is None:
            task.inicio = now
        task.conclusao = now if status == StatusTarefa.CONCLUIDO else None
        task.full_clean()
        return _persist(actor, task, 'alterar_status', before, expected_version)
    if not is_business_admin(actor) and any(
        source == task.status and destination == status and action in ADMIN_ACTIONS
        for action, (source, destination) in TRANSITIONS.items()
    ):
        _require_admin(actor)
    actions = [action for action in allowed_actions(actor, task) if TRANSITIONS[action][1] == status]
    if not actions:
        raise ValidationError({'status': 'Esta alteração não é permitida no estado atual.'})
    return transition_task(actor=actor, task_id=task_id, action=actions[0], expected_version=expected_version)
