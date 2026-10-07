from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.catalogo.models import Servico
from inovalab_app.tarefas.models import EventoTarefa, Tarefa
from inovalab_app.tarefas.selectors import visible_tasks


PUBLIC_FIELDS = {'servico', 'descricao', 'responsavel', 'prazo'}
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


def save_task(*, actor, data, task_id=None, expected_version=None):
    _require_active(actor)
    task = _load(actor, task_id, expected_version) if task_id is not None else Tarefa()
    _require_admin(actor)
    unknown = set(data) - PUBLIC_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    before = _snapshot(task) if task_id is not None else {}
    for name, value in data.items():
        if name in ('servico', 'responsavel'):
            model = Servico if name == 'servico' else get_user_model()
            if not isinstance(value, model):
                raise ValidationError({name: 'Selecione um cadastro válido.'})
            if task_id is None or value.pk != before[name]:
                criteria = {'status': 'disponivel'} if name == 'servico' else {'is_active': True}
                if not model.objects.filter(pk=value.pk, **criteria).exists():
                    raise ValidationError({name: 'Selecione um serviço disponível.' if name == 'servico'
                                           else 'Selecione um responsável ativo.'})
        setattr(task, name, value)
    task.full_clean()
    if task_id is None:
        with transaction.atomic():
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
