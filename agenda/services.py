import sqlite3
from decimal import Decimal
from datetime import datetime, timezone as dt_timezone
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.policies import is_business_admin
from agenda.models import Agendamento, ControleAgendaVisitas, EventoAgendamento
from agenda.policies import can_access_agenda
from catalogo.models import Equipamento, Espaco, Servico
from materiais.models import Material


CATEGORY_MODELS = {'servico': Servico, 'equipamento': Equipamento}
LEGACY_CATEGORY_MODELS = {**CATEGORY_MODELS, 'espaco': Espaco}
BASE_FIELDS = {'categoria', 'objeto', 'motivo', 'inicio', 'fim'}
SERVICE_FIELDS = {'equipamentos', 'material_proprio', 'material_gasto', 'material_gasto_gramas'}
PUBLIC_FIELDS = BASE_FIELDS | SERVICE_FIELDS | {'observacoes', 'quantidade_pessoas'}
STORED_FIELDS = ('servico_id', 'equipamento_id', 'espaco_id', 'visita', 'quantidade_pessoas', 'motivo', 'observacoes', 'inicio', 'fim', 'cancelado_em',
                 'material_proprio', 'material_gasto_id', 'material_gasto_gramas',
                 'situacao', 'avaliado_por_id', 'avaliado_em')


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
        if category == 'visita':
            if not ControleAgendaVisitas.objects.filter(pk=1).update(id=F('id')):
                # Também funciona após flush em testes: escreva antes de ler.
                ControleAgendaVisitas.objects.get_or_create(pk=1)
                ControleAgendaVisitas.objects.filter(pk=1).update(id=F('id'))
        elif not LEGACY_CATEGORY_MODELS[category].objects.filter(pk=pk).update(status=F('status')):
            raise ValidationError({'objeto': 'Selecione um cadastro válido.'})


def _snapshot(booking):
    values = {name: getattr(booking, name) for name in (
        'motivo', 'observacoes', 'quantidade_pessoas', 'inicio', 'fim', 'cancelado_em', 'material_proprio', 'material_gasto_gramas',
        'situacao', 'avaliado_em')}
    values.update(categoria=booking.categoria, objeto=booking.objeto_id)
    values['criado_por'] = booking.criado_por_id
    values['material_gasto'] = booking.material_gasto_id
    values['avaliado_por'] = booking.avaliado_por_id
    values['equipamentos'] = sorted(booking.equipamentos.values_list('pk', flat=True))
    return {name: value.astimezone(dt_timezone.utc).isoformat() if isinstance(value, datetime) else value
            if not isinstance(value, Decimal) else format(value, '.3f')
            for name, value in values.items()}


def _record(actor, booking, action, before, actor_name=None):
    changes = {name: {'anterior': before.get(name), 'novo': value}
               for name, value in _snapshot(booking).items() if before.get(name) != value}
    EventoAgendamento.objects.create(agendamento=booking, ator=actor, ator_nome=actor_name or actor.username,
                                    acao=action, alteracoes=changes)


def _persist_existing(booking, version):
    changed = Agendamento.objects.filter(pk=booking.pk, versao=version, cancelado_em__isnull=True).update(
        **{name: getattr(booking, name) for name in STORED_FIELDS}, versao=version + 1,
    )
    if not changed:
        raise BookingConflict('versao_desatualizada', 'O agendamento foi alterado. Atualize antes de tentar novamente.')
    booking.versao = version + 1


@_busy_as_conflict
def save_booking(*, actor, data, booking_id=None, expected_version=None, agrohub_request=None):
    if not can_access_agenda(actor):
        raise PermissionDenied('Entre com uma conta ativa para acessar a agenda.')
    if booking_id is not None:
        _require_admin(actor)
    booking = _save_booking(actor=actor, actor_name=actor.username, data=data,
                         booking_id=booking_id, expected_version=expected_version,
                         initial_status='confirmado' if is_business_admin(actor) else 'pendente', agrohub_request=agrohub_request)
    if agrohub_request is not None:
        from agenda.agrohub import sync_after_change
        sync_after_change(agrohub_request, booking)
    return booking


def _save_booking(*, actor, actor_name, data, booking_id=None, expected_version=None, initial_status='confirmado', agrohub_request=None):
    # Trusted core: role-aware facade or authenticated integration adapter only.
    unknown = set(data) - PUBLIC_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    booking = _load(booking_id, expected_version) if booking_id is not None else Agendamento(
        criado_por=actor, situacao=initial_status,
    )
    old_equipment_ids = set(booking.equipamentos.values_list('pk', flat=True)) if booking.pk else set()
    old_target = _target(booking) if booking_id is not None else None
    if booking.espaco_id is not None:
        raise ValidationError({'categoria': 'Reservas de espaços são legado: consulte ou cancele o registro.'})
    category = data.get('categoria', booking.categoria)
    if category != 'visita' and 'quantidade_pessoas' in data:
        raise ValidationError({'quantidade_pessoas': 'Quantidade de pessoas é informada somente em visitas.'})
    if category == 'visita':
        extra = set(data) & ({'objeto', 'motivo', 'observacoes'} | SERVICE_FIELDS)
        if extra:
            raise ValidationError({name: 'Visitas possuem somente dia, horários e quantidade de pessoas.' for name in extra})
    elif ('categoria' in data) != ('objeto' in data):
        raise ValidationError({'objeto': 'Informe categoria e objeto juntos.'})
    if 'categoria' in data:
        if not isinstance(category, str) or category not in (*CATEGORY_MODELS, 'visita'):
            raise ValidationError({'categoria': 'Selecione uma categoria válida.'})
        pk = data.get('objeto')
        if category != 'visita' and (type(pk) is not int or pk < 1):
            raise ValidationError({'objeto': 'Informe um ID inteiro positivo.'})
        booking.visita = category == 'visita'
        for name in LEGACY_CATEGORY_MODELS:
            setattr(booking, name + '_id', pk if name == category else None)
        if booking.visita:
            booking.motivo = booking.observacoes = ''
    if booking.categoria is None:
        raise ValidationError({'objeto': 'Selecione categoria e objeto.'})
    if booking.visita:
        booking.quantidade_pessoas = data.get('quantidade_pessoas', booking.quantidade_pessoas if booking.quantidade_pessoas is not None else 1)
        if type(booking.quantidade_pessoas) is not int or not 1 <= booking.quantidade_pessoas <= 2147483647:
            raise ValidationError({'quantidade_pessoas': 'Informe uma quantidade inteira de pelo menos 1 pessoa.'})
    else:
        booking.quantidade_pessoas = None
    equipment_ids = data.get('equipamentos', sorted(old_equipment_ids))
    if not isinstance(equipment_ids, (list, tuple)) or any(type(pk) is not int or pk < 1 for pk in equipment_ids):
        raise ValidationError({'equipamentos': 'Informe uma lista de IDs inteiros positivos.'})
    if len(set(equipment_ids)) != len(equipment_ids):
        raise ValidationError({'equipamentos': 'Selecione cada equipamento uma única vez.'})
    if booking.categoria != 'servico':
        if any(data.get(name) not in (None, []) for name in SERVICE_FIELDS):
            raise ValidationError({'equipamentos': 'Estes campos são exclusivos de agendamentos de serviço.'})
        equipment_ids = []
        booking.material_proprio = None
        booking.material_gasto_id = None
        booking.material_gasto_gramas = None
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
    if agrohub_request is not None and booking.visita and actor.agrohub_id is not None:
        from agenda.agrohub import validate_before_save
        booking.full_clean()
        validate_before_save(agrohub_request, booking, allow_create=old_target is None or old_target[0] != 'visita')
    with transaction.atomic():
        _lock_targets(*(item for item in (old_target, target) if item is not None),
                      *(('equipamento', pk) for pk in set(equipment_ids) | old_equipment_ids))
        previous = _load(booking_id, expected_version) if booking_id is not None else None
        before = _snapshot(previous) if previous else {}
        resource = CATEGORY_MODELS[target[0]].objects.get(pk=target[1]) if not booking.visita else None
        period_changed = previous is None or target != _target(previous) or (booking.inicio, booking.fim) != (previous.inicio, previous.fim)
        if period_changed and resource is not None and resource.status == 'indisponivel':
            raise ValidationError({'objeto': 'Este cadastro está indisponível para reservar este período.'})
        if Equipamento.objects.filter(pk__in=equipment_ids, status='indisponivel').filter(
                ~Q(pk__in=old_equipment_ids) if not period_changed else Q()).exists():
            raise ValidationError({'equipamentos': 'Um equipamento selecionado está indisponível.'})
        if booking.material_gasto_id is not None:
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
        booking.equipamentos.set(equipment_ids)
        from agenda.agrohub import queue_reservation
        queue_reservation(booking, actor, allow_create=previous is None or not previous.visita)
        _record(actor, booking, 'editar' if previous else 'criar', before, actor_name=actor_name)
    return booking


def _check_overlap(booking):
    target_filter = {'visita': True} if booking.visita else {booking.categoria + '_id': booking.objeto_id}
    overlap = Agendamento.objects.filter(situacao='confirmado', cancelado_em__isnull=True,
        inicio__lt=booking.fim, fim__gt=booking.inicio, **target_filter)
    if booking.pk:
        overlap = overlap.exclude(pk=booking.pk)
    if overlap.exists():
        raise BookingConflict('horario_ocupado', 'Já existe uma visita no período informado.' if booking.visita
                              else 'Já existe uma reserva deste objeto no período informado.')


@_busy_as_conflict
def review_booking(*, actor, booking_id, expected_version, decision, agrohub_request=None):
    _require_admin(actor)
    if decision not in ('aprovar', 'rejeitar'):
        raise ValidationError({'decisao': 'Escolha aceitar ou rejeitar a solicitação.'})
    booking = _load(booking_id, expected_version)
    equipment_ids = list(booking.equipamentos.values_list('pk', flat=True))
    with transaction.atomic():
        _lock_targets(_target(booking), *(('equipamento', pk) for pk in equipment_ids))
        booking = _load(booking_id, expected_version)
        if booking.situacao != 'pendente':
            raise BookingConflict('pedido_avaliado', 'Esta solicitação já foi avaliada.')
        before = _snapshot(booking)
        if decision == 'aprovar':
            if booking.espaco_id is not None:
                raise ValidationError({'categoria': 'Reservas de espaços são legado e não podem ser aprovadas.'})
            resource = CATEGORY_MODELS[booking.categoria].objects.get(pk=booking.objeto_id) if not booking.visita else None
            if resource is not None and resource.status == 'indisponivel':
                raise ValidationError({'objeto': 'Este cadastro está indisponível para reservar este período.'})
            if Equipamento.objects.filter(pk__in=equipment_ids, status='indisponivel').exists():
                raise ValidationError({'equipamentos': 'Um equipamento selecionado está indisponível.'})
            if booking.material_gasto_id is not None:
                material = Material.objects.select_for_update().get(pk=booking.material_gasto_id)
                if material.status == 'indisponivel':
                    raise ValidationError({'material_gasto': 'Este material está indisponível.'})
            booking.full_clean()
            _check_overlap(booking)
        booking.situacao = 'confirmado' if decision == 'aprovar' else 'rejeitado'
        booking.avaliado_por = actor
        booking.avaliado_em = timezone.now()
        _persist_existing(booking, expected_version)
        from agenda.agrohub import queue_reservation
        queue_reservation(booking, actor)
        _record(actor, booking, decision, before)
    if agrohub_request is not None:
        from agenda.agrohub import sync_after_change
        sync_after_change(agrohub_request, booking)
    return booking


@_busy_as_conflict
def cancel_booking(*, actor, booking_id, expected_version, agrohub_request=None):
    _require_admin(actor)
    booking = _load(booking_id, expected_version)
    with transaction.atomic():
        _lock_targets(_target(booking))
        booking = _load(booking_id, expected_version)
        before = _snapshot(booking)
        booking.cancelado_em = timezone.now()
        _persist_existing(booking, expected_version)
        from agenda.agrohub import queue_reservation
        queue_reservation(booking, actor)
        _record(actor, booking, 'cancelar', before)
    if agrohub_request is not None:
        from agenda.agrohub import sync_after_change
        sync_after_change(agrohub_request, booking)
    return booking
