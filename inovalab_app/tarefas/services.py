import sqlite3
from functools import wraps
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.agenda.models import AgendaServico
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.models import EventoTarefa, StatusTarefa, Tarefa
from inovalab_app.tarefas.selectors import visible_tasks


PUBLIC_FIELDS = {'agendamento_servico', 'descricao', 'responsavel', 'equipamento', 'material_gasto', 'quantidade_material_gasto'}
TRACKED_FIELDS = (*sorted(PUBLIC_FIELDS), 'status', 'inicio', 'conclusao', 'excluida_em')
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
    return values


def _record(actor, task, action, before):
    after = _snapshot(task)
    changes = {key: {'anterior': before.get(key), 'novo': value}
               for key, value in after.items() if before.get(key) != value}
    EventoTarefa.objects.create(
        tarefa=task, ator=actor, ator_nome=actor.username, acao=action,
        status_anterior=before.get('status', ''), status_novo=task.status, alteracoes=changes,
    )


@transaction.atomic
def _persist(actor, task, action, before, expected_version):
    # A conditional UPDATE provides version protection on SQLite too.
    values = {name: getattr(task, task._meta.get_field(name).attname) for name in TRACKED_FIELDS}
    values['versao'] = expected_version + 1
    changed = Tarefa.objects.filter(pk=task.pk, versao=expected_version, excluida_em__isnull=True).update(**values)
    if not changed:
        raise TaskConflict('A tarefa foi alterada. Atualize a página antes de tentar novamente.')
    task.versao = expected_version + 1
    _record(actor, task, action, before)
    return task


def allowed_actions(actor, task):
    if not actor.is_authenticated or not actor.is_active or task.excluida_em:
        return []
    admin = is_business_admin(actor)
    if not admin and task.responsavel_id != actor.pk:
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
    for name, model, field in (('equipamento', Equipamento, 'status'),
                               ('material_gasto', Material, 'quantidade'),
                               ('responsavel', get_user_model(), 'is_active')):
        pk = getattr(task, name + '_id')
        if pk is not None and not model.objects.filter(pk=pk).update(**{field: F(field)}):
            raise ValidationError({name: 'Selecione um cadastro válido.'})


@_busy_as_task_conflict
def save_task(*, actor, data, task_id=None, expected_version=None):
    _require_active(actor)
    task = _load(actor, task_id, expected_version) if task_id is not None else Tarefa()
    _require_admin(actor)
    unknown = set(data) - PUBLIC_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    before = _snapshot(task) if task_id is not None else {}
    references = {'agendamento_servico': AgendaServico, 'responsavel': get_user_model(),
                  'equipamento': Equipamento, 'material_gasto': Material}
    for name, value in data.items():
        if name in references and not (value is None and name in ('equipamento', 'material_gasto')):
            if not isinstance(value, references[name]) or value.pk is None:
                raise ValidationError({name: 'Selecione um cadastro válido.'})
        setattr(task, name, value)
    with transaction.atomic():
        _lock_references(task)
        for name, model in references.items():
            pk = getattr(task, name + '_id')
            if pk is None or (task_id is not None and pk == before[name]):
                continue
            criteria = {'agendamento_servico': {'situacao': 'confirmado', 'cancelado_em__isnull': True},
                        'responsavel': {'is_active': True}, 'equipamento': {'excluido_em__isnull': True},
                        'material_gasto': {'status': 'disponivel'}}[name]
            if not model.objects.filter(pk=pk, **criteria).exists():
                raise ValidationError({name: 'Selecione um agendamento confirmado e não cancelado.' if name == 'agendamento_servico'
                                       else 'Selecione um cadastro ativo e disponível.'})
        task.full_clean()
        if task_id is None:
            task.save()
            _record(actor, task, 'criar', before)
            return task
        return _persist(actor, task, 'editar', before, expected_version)


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
    if not is_business_admin(actor) and task.responsavel_id != actor.pk:
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
