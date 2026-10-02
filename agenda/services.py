import sqlite3
from datetime import datetime, timezone as dt_timezone
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.policies import is_business_admin
from agenda.models import Agendamento, EventoAgendamento
from catalogo.models import Equipamento, Espaco, Servico


CATEGORY_MODELS = {'servico': Servico, 'equipamento': Equipamento, 'espaco': Espaco}
PUBLIC_FIELDS = {'categoria', 'objeto', 'requerente', 'motivo', 'inicio', 'fim'}
STORED_FIELDS = ('servico_id', 'equipamento_id', 'espaco_id', 'requerente', 'motivo', 'inicio', 'fim', 'cancelado_em')


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
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem acessar a agenda.')


def _check_version(booking, version):
    if type(version) is not int or version < 1:
        raise ValidationError({'versao': 'Informe a versão inteira positiva do agendamento.'})
    if booking.versao != version:
        raise BookingConflict('versao_desatualizada', 'O agendamento foi alterado. Atualize antes de tentar novamente.')


def _load(booking_id, version):
    booking = get_object_or_404(Agendamento, pk=booking_id, cancelado_em__isnull=True)
    _check_version(booking, version)
    return booking


def _target(booking):
    return (booking.categoria, booking.objeto_id)


def _lock_targets(*targets):
    # First database access inside atomic: acquire write locks before reading conflicts.
    # A no-op UPDATE also works on SQLite, where select_for_update is ineffective.
    for category, pk in sorted(set(targets)):
        if not CATEGORY_MODELS[category].objects.filter(pk=pk).update(status=F('status')):
            raise ValidationError({'objeto': 'Selecione um cadastro válido.'})


def _snapshot(booking):
    values = {name: getattr(booking, name) for name in ('requerente', 'motivo', 'inicio', 'fim', 'cancelado_em')}
    values.update(categoria=booking.categoria, objeto=booking.objeto_id)
    return {name: value.astimezone(dt_timezone.utc).isoformat() if isinstance(value, datetime) else value
            for name, value in values.items()}


def _record(actor, booking, action, before):
    changes = {name: {'anterior': before.get(name), 'novo': value}
               for name, value in _snapshot(booking).items() if before.get(name) != value}
    EventoAgendamento.objects.create(agendamento=booking, ator=actor, ator_nome=actor.username,
                                    acao=action, alteracoes=changes)


def _persist_existing(booking, version):
    changed = Agendamento.objects.filter(pk=booking.pk, versao=version, cancelado_em__isnull=True).update(
        **{name: getattr(booking, name) for name in STORED_FIELDS}, versao=version + 1,
    )
    if not changed:
        raise BookingConflict('versao_desatualizada', 'O agendamento foi alterado. Atualize antes de tentar novamente.')
    booking.versao = version + 1


@_busy_as_conflict
def save_booking(*, actor, data, booking_id=None, expected_version=None):
    _require_admin(actor)
    unknown = set(data) - PUBLIC_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    booking = _load(booking_id, expected_version) if booking_id is not None else Agendamento(criado_por=actor)
    old_target = _target(booking) if booking_id is not None else None
    if ('categoria' in data) != ('objeto' in data):
        raise ValidationError({'objeto': 'Informe categoria e objeto juntos.'})
    if 'categoria' in data:
        category, pk = data['categoria'], data['objeto']
        if not isinstance(category, str) or category not in CATEGORY_MODELS:
            raise ValidationError({'categoria': 'Selecione uma categoria válida.'})
        if type(pk) is not int or pk < 1:
            raise ValidationError({'objeto': 'Informe um ID inteiro positivo.'})
        for name in CATEGORY_MODELS:
            setattr(booking, name + '_id', pk if name == category else None)
    if booking.categoria is None:
        raise ValidationError({'objeto': 'Selecione categoria e objeto.'})
    for name in ('requerente', 'motivo', 'inicio', 'fim'):
        if name in data:
            setattr(booking, name, data[name])
    target = _target(booking)
    with transaction.atomic():
        _lock_targets(*(item for item in (old_target, target) if item is not None))
        previous = _load(booking_id, expected_version) if booking_id is not None else None
        before = _snapshot(previous) if previous else {}
        resource = CATEGORY_MODELS[target[0]].objects.get(pk=target[1])
        period_changed = previous is None or target != _target(previous) or (booking.inicio, booking.fim) != (previous.inicio, previous.fim)
        if period_changed and resource.status == 'indisponivel':
            raise ValidationError({'objeto': 'Este cadastro está indisponível para reservar este período.'})
        booking.full_clean()
        overlap = Agendamento.objects.filter(cancelado_em__isnull=True, inicio__lt=booking.fim, fim__gt=booking.inicio,
                                             **{target[0] + '_id': target[1]})
        if previous:
            overlap = overlap.exclude(pk=booking.pk)
        if overlap.exists():
            raise BookingConflict('horario_ocupado', 'Já existe uma reserva deste objeto no período informado.')
        if previous:
            _persist_existing(booking, expected_version)
        else:
            booking.save()
        _record(actor, booking, 'editar' if previous else 'criar', before)
    return booking


@_busy_as_conflict
def cancel_booking(*, actor, booking_id, expected_version):
    _require_admin(actor)
    booking = _load(booking_id, expected_version)
    with transaction.atomic():
        _lock_targets(_target(booking))
        booking = _load(booking_id, expected_version)
        before = _snapshot(booking)
        booking.cancelado_em = timezone.now()
        _persist_existing(booking, expected_version)
        _record(actor, booking, 'cancelar', before)
    return booking
