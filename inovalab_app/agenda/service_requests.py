from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.agenda.models import AgendaServico
from inovalab_app.catalogo.models import Servico

SERVICE_REQUEST_FIELDS = {'categoria', 'titulo', 'descricao', 'prazo', 'observacoes'}


@transaction.atomic
def save_service_request(*, actor, data, booking_id=None, expected_version=None):
    from inovalab_app.agenda.services import _load, _snapshot, _persist_existing, _record
    from inovalab_app.agenda.policies import can_create_booking
    if not can_create_booking(actor):
        raise PermissionDenied('Entre com uma conta ativa para solicitar serviços.')
    if booking_id is not None and not is_business_admin(actor):
        raise PermissionDenied('Somente administradores podem editar agendamentos.')
    unknown = set(data) - SERVICE_REQUEST_FIELDS
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    if data.get('categoria', 'servico') != 'servico':
        raise ValidationError({'categoria': 'A categoria não pode ser alterada.'})
    if booking_id is None:
        service = Servico()
        booking = AgendaServico(criado_por=actor, situacao='confirmado' if is_business_admin(actor) else 'pendente')
        before = {}
    else:
        booking = _load(booking_id, expected_version, 'servico')
        before = _snapshot(booking)
        service = Servico.objects.select_for_update().get(pk=booking.servico_id)
    for name in ('titulo', 'descricao', 'prazo'):
        if name in data:
            setattr(service, name, data[name])
    service.full_clean()
    if 'observacoes' in data:
        booking.observacoes = data['observacoes']
    if booking_id is not None:
        # Claim the version before saving the mutable service; all writes roll back together.
        _persist_existing(booking, expected_version)
    service.save()
    booking.servico = service
    booking.full_clean()
    if booking_id is None:
        booking.save()
    _record(actor, booking, 'editar' if booking_id is not None else 'criar', before)
    return booking
