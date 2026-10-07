import sqlite3
from decimal import Decimal
from datetime import date, time, datetime, timezone as dt_timezone
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone

from accounts.policies import is_business_admin
from agenda.models import BOOKING_MODELS, AgendaVisita, EventoAgendamento
from agenda.policies import can_access_agenda
from catalogo.models import Equipamento, Servico
from materiais.models import Material


CATEGORY_MODELS = {'servico': Servico, 'equipamento': Equipamento}
BASE_FIELDS = {'categoria', 'objeto', 'motivo', 'inicio', 'fim'}
SERVICE_FIELDS = {'equipamentos', 'material_proprio', 'material_gasto', 'material_gasto_gramas'}
PUBLIC_FIELDS = BASE_FIELDS | SERVICE_FIELDS | {'observacoes'}
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
        if not CATEGORY_MODELS[category].objects.filter(pk=pk).update(status=F('status')):
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
    values['criado_por'] = booking.criado_por_id
    if booking.categoria == 'servico':
        values.update(material_gasto=booking.material_gasto_id, material_proprio=booking.material_proprio,
                      material_gasto_gramas=booking.material_gasto_gramas,
                      equipamentos=sorted(booking.equipamentos.values_list('pk', flat=True)))
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
    if not can_access_agenda(actor):
        raise PermissionDenied('Entre com uma conta ativa para acessar a agenda.')
    if booking_id is not None:
        _require_admin(actor)
    if (category or data.get('categoria')) == 'visita':
        return _save_visit(actor=actor, data=data, booking_id=booking_id, expected_version=expected_version)
    booking = _save_booking(actor=actor, actor_name=actor.username, data=data,
                         category=category, booking_id=booking_id, expected_version=expected_version,
                         initial_status='confirmado' if is_business_admin(actor) else 'pendente')
    return booking


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


def _save_booking(*, actor, actor_name, data, category=None, booking_id=None, expected_version=None, initial_status='confirmado'):
    # Trusted core: role-aware facade or authenticated integration adapter only.
    unknown = set(data) - PUBLIC_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    if booking_id is not None:
        booking = _load(booking_id, expected_version, category)
        if 'categoria' in data and data['categoria'] != category:
            raise ValidationError({'categoria': 'A categoria do agendamento não pode ser alterada.'})
    else:
        category = data.get('categoria', category)
        booking = booking_model(category)(criado_por=actor, situacao=initial_status)
    old_equipment_ids = set(booking.equipamentos.values_list('pk', flat=True)) if booking.pk and category == 'servico' else set()
    old_target = _target(booking) if booking_id is not None else None
    if ('categoria' in data) != ('objeto' in data):
        raise ValidationError({'objeto': 'Informe categoria e objeto juntos.'})
    if 'objeto' in data:
        pk = data['objeto']
        if type(pk) is not int or pk < 1:
            raise ValidationError({'objeto': 'Informe um ID inteiro positivo.'})
        setattr(booking, category + '_id', pk)
    if booking.objeto_id is None:
        raise ValidationError({'objeto': 'Selecione categoria e objeto.'})
    equipment_ids = data.get('equipamentos', sorted(old_equipment_ids))
    if not isinstance(equipment_ids, (list, tuple)) or any(type(pk) is not int or pk < 1 for pk in equipment_ids):
        raise ValidationError({'equipamentos': 'Informe uma lista de IDs inteiros positivos.'})
    if len(set(equipment_ids)) != len(equipment_ids):
        raise ValidationError({'equipamentos': 'Selecione cada equipamento uma única vez.'})
    if booking.categoria != 'servico':
        if any(data.get(name) not in (None, []) for name in SERVICE_FIELDS):
            raise ValidationError({'equipamentos': 'Estes campos são exclusivos de agendamentos de serviço.'})
        equipment_ids = []
    else:
        for name in ('material_proprio', 'material_gasto_gramas'):
            if name in data:
                setattr(booking, name, data[name])
        if booking.material_proprio is not None and type(booking.material_proprio) is not bool:
            raise ValidationError({'material_proprio': 'Informe sim ou não.'})
        if booking.material_proprio is True and 'material_gasto_gramas' not in data:
            booking.material_gasto_gramas = None
        if 'material_gasto' in data:
            material_id = data['material_gasto']
            if material_id is not None and (type(material_id) is not int or material_id < 1):
                raise ValidationError({'material_gasto': 'Selecione um material válido.'})
            booking.material_gasto_id = material_id
        elif booking.material_proprio is True:
            booking.material_gasto_id = None
    for name in ('motivo', 'observacoes', 'inicio', 'fim'):
        if name in data:
            setattr(booking, name, data[name])
    target = _target(booking)
    with transaction.atomic():
        _lock_targets(*(item for item in (old_target, target) if item is not None),
                      *(('equipamento', pk) for pk in set(equipment_ids) | old_equipment_ids))
        previous = _load(booking_id, expected_version, category) if booking_id is not None else None
        before = _snapshot(previous) if previous else {}
        resource = CATEGORY_MODELS[target[0]].objects.get(pk=target[1])
        period_changed = previous is None or target != _target(previous) or (booking.inicio, booking.fim) != (previous.inicio, previous.fim)
        if period_changed and resource is not None and resource.status == 'indisponivel':
            raise ValidationError({'objeto': 'Este cadastro está indisponível para reservar este período.'})
        if Equipamento.objects.filter(pk__in=equipment_ids, status='indisponivel').filter(
                ~Q(pk__in=old_equipment_ids) if not period_changed else Q()).exists():
            raise ValidationError({'equipamentos': 'Um equipamento selecionado está indisponível.'})
        if category == 'servico' and booking.material_gasto_id is not None:
            material = Material.objects.select_for_update().filter(pk=booking.material_gasto_id).first()
            if material is None:
                raise ValidationError({'material_gasto': 'Selecione um material válido.'})
            if material.status == 'indisponivel' and (period_changed or previous.material_gasto_id != material.pk):
                raise ValidationError({'material_gasto': 'Este material está indisponível.'})
        booking.full_clean()
        if booking.situacao == 'confirmado':
            _check_overlap(booking)
        if previous:
            _persist_existing(booking, expected_version)
        else:
            booking.save()
        if category == 'servico':
            booking.equipamentos.set(equipment_ids)
        _record(actor, booking, 'editar' if previous else 'criar', before, actor_name=actor_name)
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
def review_booking(*, actor, category, booking_id, expected_version, decision):
    _require_admin(actor)
    if decision not in ('aprovar', 'rejeitar'):
        raise ValidationError({'decisao': 'Escolha aceitar ou rejeitar a solicitação.'})
    booking = _load(booking_id, expected_version, category)
    equipment_ids = list(booking.equipamentos.values_list('pk', flat=True)) if category == 'servico' else []
    with transaction.atomic():
        _lock_targets(_target(booking), *(('equipamento', pk) for pk in equipment_ids))
        booking = _load(booking_id, expected_version, category)
        if booking.situacao != 'pendente':
            raise BookingConflict('pedido_avaliado', 'Esta solicitação já foi avaliada.')
        before = _snapshot(booking)
        if decision == 'aprovar':
            resource = CATEGORY_MODELS[booking.categoria].objects.get(pk=booking.objeto_id) if category != 'visita' else None
            if resource is not None and resource.status == 'indisponivel':
                raise ValidationError({'objeto': 'Este cadastro está indisponível para reservar este período.'})
            if Equipamento.objects.filter(pk__in=equipment_ids, status='indisponivel').exists():
                raise ValidationError({'equipamentos': 'Um equipamento selecionado está indisponível.'})
            if category == 'servico' and booking.material_gasto_id is not None:
                material = Material.objects.select_for_update().get(pk=booking.material_gasto_id)
                if material.status == 'indisponivel':
                    raise ValidationError({'material_gasto': 'Este material está indisponível.'})
            booking.full_clean()
            _check_overlap(booking)
        booking.situacao = 'confirmado' if decision == 'aprovar' else 'rejeitado'
        booking.avaliado_por = actor
        booking.avaliado_em = timezone.now()
        _persist_existing(booking, expected_version)
        _record(actor, booking, decision, before)
    return booking


@_busy_as_conflict
def cancel_booking(*, actor, category, booking_id, expected_version):
    _require_admin(actor)
    booking = _load(booking_id, expected_version, category)
    with transaction.atomic():
        _lock_targets(_target(booking))
        booking = _load(booking_id, expected_version, category)
        before = _snapshot(booking)
        booking.cancelado_em = timezone.now()
        _persist_existing(booking, expected_version)
        _record(actor, booking, 'cancelar', before)
    return booking
