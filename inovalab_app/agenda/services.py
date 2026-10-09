import sqlite3
from collections.abc import Mapping
from decimal import Decimal
from datetime import date, time, datetime, timezone as dt_timezone
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.agenda.models import BOOKING_MODELS, AgendaVisita, EventoAgendamento
from inovalab_app.agenda.policies import ADMIN_CANCEL_MESSAGE, can_access_agenda, can_create_booking, can_cancel_booking
from inovalab_app.catalogo.models import Equipamento, Servico
from inovalab_app.materiais.models import Material


CATEGORY_MODELS = {'servico': Servico, 'equipamento': Equipamento}
PUBLIC_FIELDS = {'categoria', 'titulo', 'descricao', 'prazo', 'observacoes'}
VISIT_FIELDS = {'categoria', 'quantidade_pessoas', 'data', 'hora_inicio', 'hora_termino', 'observacoes'}



class BookingConflict(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _busy_as_conflict(operation):
    @wraps(operation)
    def wrapped(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except OperationalError as error:
            code = getattr(error.__cause__, 'sqlite_errorcode', 0)
            if connection.vendor == 'sqlite' and (code & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise BookingConflict('agenda_ocupada', 'A agenda está sendo alterada. Atualize e tente novamente.') from error
            raise
    return wrapped


def _require_admin(actor):
    if not can_access_agenda(actor) or not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem acessar a agenda.')


def _check_version(booking, version):
    if type(version) is not int or version < 1:
        raise ValidationError({'versao': 'Informe a versão inteira positiva do agendamento.'})
    if booking.versao != version:
        raise BookingConflict('versao_desatualizada', 'O agendamento foi alterado. Atualize antes de tentar novamente.')


def booking_model(category):
    if category not in BOOKING_MODELS:
        raise ValidationError({'categoria': 'Selecione serviço, equipamento ou visita.'})
    return BOOKING_MODELS[category]


def _load(booking_id, version, category):
    booking = get_object_or_404(booking_model(category), pk=booking_id, cancelado_em__isnull=True)
    _check_version(booking, version)
    return booking


def _target(booking):
    return (booking.categoria, booking.objeto_id)


def _lock_targets(*targets):
    # First database access inside atomic: acquire write locks before reading conflicts.
    # A no-op UPDATE also works on SQLite, where select_for_update is ineffective.
    for category, pk in sorted(set(targets)):
        if category == 'visita':
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', [718304261])
            else:
                AgendaVisita.objects.all().update(versao=F('versao'))
            continue
        field = 'titulo' if category == 'servico' else 'status'
        if not CATEGORY_MODELS[category].objects.filter(pk=pk).update(**{field: F(field)}):
            raise ValidationError({'objeto': 'Selecione um cadastro válido.'})


def _snapshot(booking):
    values = {name: getattr(booking, name) for name in (
        'motivo', 'observacoes', 'inicio', 'fim', 'cancelado_em',
        'situacao', 'avaliado_em')}
    values.update(categoria=booking.categoria, objeto=booking.objeto_id)
    if booking.categoria == 'visita':
        values.pop('motivo')
        values.pop('objeto')
        values.update({name: getattr(booking, name) for name in VISIT_FIELDS - {'categoria', 'observacoes'}})
        values.update(realizada_em=booking.realizada_em, realizada_por=booking.realizada_por_id)
    values['criado_por'] = booking.criado_por_id
    if booking.categoria == 'servico':
        values.update(titulo=booking.servico.titulo, descricao=booking.servico.descricao, prazo=booking.servico.prazo)
        for name in ('motivo', 'inicio', 'fim', 'objeto'):
            values.pop(name, None)
    values['avaliado_por'] = booking.avaliado_por_id
    return {name: value.astimezone(dt_timezone.utc).isoformat() if isinstance(value, datetime)
            else value.isoformat() if isinstance(value, (date, time))
            else format(value, '.3f') if isinstance(value, Decimal) else value
            for name, value in values.items()}


def _record(actor, booking, action, before, actor_name=None):
    changes = {name: {'anterior': before.get(name), 'novo': value}
               for name, value in _snapshot(booking).items() if before.get(name) != value}
    EventoAgendamento.objects.create(**{'agenda_' + booking.categoria: booking}, ator=actor, ator_nome=actor_name or actor.username,
                                    acao=action, alteracoes=changes)


def _persist_existing(booking, version):
    changed = type(booking).objects.filter(pk=booking.pk, versao=version, cancelado_em__isnull=True).update(
        **{name: getattr(booking, name) for name in [field.attname for field in booking._meta.concrete_fields
                     if field.name not in ('id', 'versao', 'criado_por', 'criado_em')]}, versao=version + 1,
    )
    if not changed:
        raise BookingConflict('versao_desatualizada', 'O agendamento foi alterado. Atualize antes de tentar novamente.')
    booking.versao = version + 1


@_busy_as_conflict
def save_booking(*, actor, data, category=None, booking_id=None, expected_version=None):
    if not can_create_booking(actor):
        raise PermissionDenied('Entre com uma conta ativa para acessar a agenda.')
    if booking_id is not None:
        _require_admin(actor)
    if (category or data.get('categoria')) == 'visita':
        return _save_visit(actor=actor, data=data, booking_id=booking_id, expected_version=expected_version)
    if (category or data.get('categoria')) == 'servico':
        from inovalab_app.agenda.service_requests import save_service_request
        return save_service_request(actor=actor, data=data, booking_id=booking_id, expected_version=expected_version)
    raise ValidationError({'categoria': 'Equipamentos não podem ser agendados. Selecione serviço ou visita.'})


def _save_visit(*, actor, data, booking_id=None, expected_version=None):
    unknown = set(data) - VISIT_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    if data.get('categoria', 'visita') != 'visita':
        raise ValidationError({'categoria': 'A categoria do agendamento não pode ser alterada.'})
    with transaction.atomic():
        _lock_targets(('visita', 0))
        booking = _load(booking_id, expected_version, 'visita') if booking_id is not None else AgendaVisita(
            criado_por=actor, situacao='confirmado' if is_business_admin(actor) else 'pendente')
        before = _snapshot(booking) if booking_id is not None else {}
        for name in VISIT_FIELDS - {'categoria'}:
            if name in data:
                setattr(booking, name, data[name])
        if type(booking.quantidade_pessoas) is not int or not 1 <= booking.quantidade_pessoas <= 2147483647:
            raise ValidationError({'quantidade_pessoas': 'Informe uma quantidade inteira positiva.'})
        if type(booking.data) is not date:
            raise ValidationError({'data': 'Informe uma data válida.'})
        for name in ('hora_inicio', 'hora_termino'):
            value = getattr(booking, name)
            if not isinstance(value, time) or value.tzinfo is not None:
                raise ValidationError({name: 'Informe um horário válido de Brasília.'})
        booking.full_clean()
        if booking.situacao == 'confirmado':
            _check_overlap(booking)
        if booking_id is not None:
            _persist_existing(booking, expected_version)
        else:
            booking.save()
        _record(actor, booking, 'editar' if booking_id is not None else 'criar', before)
        return booking


def _check_overlap(booking):
    if booking.categoria == 'visita':
        overlap = AgendaVisita.objects.filter(situacao='confirmado', cancelado_em__isnull=True,
            data=booking.data, hora_inicio__lt=booking.hora_termino, hora_termino__gt=booking.hora_inicio)
    else:
        overlap = type(booking).objects.filter(situacao='confirmado', cancelado_em__isnull=True,
            inicio__lt=booking.fim, fim__gt=booking.inicio, **{booking.categoria + '_id': booking.objeto_id})
    if booking.pk:
        overlap = overlap.exclude(pk=booking.pk)
    if overlap.exists():
        message = ('Já existe uma visita confirmada no período informado.' if booking.categoria == 'visita'
                   else 'Já existe uma reserva deste objeto no período informado.')
        raise BookingConflict('horario_ocupado', message)


@_busy_as_conflict
def review_booking(*, actor, category, booking_id, expected_version, decision, task_data=None):
    _require_admin(actor)
    if decision not in ('aprovar', 'rejeitar'):
        raise ValidationError({'decisao': 'Escolha aceitar ou rejeitar a solicitação.'})
    booking = _load(booking_id, expected_version, category)
    if category == 'equipamento':
        raise ValidationError({'categoria': 'Agendamentos de equipamento são somente históricos.'})
    with transaction.atomic():
        _lock_targets(_target(booking))
        booking = _load(booking_id, expected_version, category)
        if booking.situacao != 'pendente':
            raise BookingConflict('pedido_avaliado', 'Esta solicitação já foi avaliada.')
        if category == 'servico' and decision == 'aprovar':
            if not isinstance(task_data, Mapping):
                raise ValidationError({'tarefa': 'Crie uma tarefa vinculada para confirmar o serviço.'})
            if 'agendamento_servico' in task_data:
                raise ValidationError({'tarefa': 'O serviço da tarefa é definido pela solicitação em confirmação.'})
        before = _snapshot(booking)
        if decision == 'aprovar':
            booking.full_clean()
            if category == 'visita':
                _check_overlap(booking)
        booking.situacao = 'confirmado' if decision == 'aprovar' else 'rejeitado'
        booking.avaliado_por = actor
        booking.avaliado_em = timezone.now()
        _persist_existing(booking, expected_version)
        if category == 'servico' and decision == 'aprovar':
            from inovalab_app.tarefas.services import save_task, TaskConflict
            try:
                # The confirmed state is visible only inside this transaction.
                # Any task/link/history failure rolls back the approval too.
                booking.created_task = save_task(actor=actor, data={**task_data, 'agendamento_servico': booking})
            except TaskConflict as error:
                raise BookingConflict('registros_em_alteracao', str(error)) from error
        _record(actor, booking, decision, before)
    return booking


@_busy_as_conflict
def mark_visit_realized(*, actor, booking_id, expected_version):
    _require_admin(actor)
    with transaction.atomic():
        _lock_targets(('visita', 0))
        booking = _load(booking_id, expected_version, 'visita')
        if booking.situacao != 'confirmado':
            raise BookingConflict('visita_nao_confirmada', 'Somente visitas confirmadas podem ser marcadas como realizadas.')
        if booking.realizada_em is not None:
            raise BookingConflict('visita_realizada', 'A realização desta visita já foi registrada. Atualize os dados.')
        now = timezone.now()
        if now < booking.inicio:
            raise ValidationError({'realizacao': 'A visita pode ser marcada como realizada a partir do início.'})
        before = _snapshot(booking)
        booking.realizada_em, booking.realizada_por = now, actor
        _persist_existing(booking, expected_version)
        _record(actor, booking, 'realizar', before)
    return booking


@_busy_as_conflict
def cancel_booking(*, actor, category, booking_id, expected_version):
    if not can_create_booking(actor):
        raise PermissionDenied('Entre com uma conta ativa para cancelar agendamentos.')

    def load_owned_booking():
        booking = get_object_or_404(booking_model(category), pk=booking_id, cancelado_em__isnull=True)
        if not can_cancel_booking(actor, booking):
            raise PermissionDenied(ADMIN_CANCEL_MESSAGE if is_business_admin(actor) else
                                   'Você pode cancelar somente seus próprios agendamentos.')
        _check_version(booking, expected_version)
        return booking

    booking = load_owned_booking()
    with transaction.atomic():
        _lock_targets(_target(booking))
        booking = load_owned_booking()
        before = _snapshot(booking)
        booking.cancelado_em = timezone.now()
        _persist_existing(booking, expected_version)
        _record(actor, booking, 'cancelar', before)
    return booking
