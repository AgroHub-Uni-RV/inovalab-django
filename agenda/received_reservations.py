"""Conciliação das reservas do AgroHub com a agenda, sem reenviar reservas."""
from django.db import transaction
from django.utils import timezone

from accounts.agrohub.client import base_url
from agenda.models import Agendamento, EventoAgendamento, ReservaAgroHub
from agenda.services import _busy_as_conflict, _lock_targets


@_busy_as_conflict
def reconcile_reservations(rows):
    origin = base_url()
    with transaction.atomic():
        _lock_targets(('visita', None))
        links = {link.reserva_id: link for link in ReservaAgroHub.objects.filter(
            origem=origin, reserva_id__in=[row.id for row in rows]).select_related('agendamento')}
        for row in rows:
            link = links.get(row.id)
            if link is None and row.status != 'confirmada':
                continue
            # Intenções locais ainda não enviadas não são substituídas por uma leitura remota.
            if link is not None and not link.recebida and (link.estado != 'registrada' or not link.agendamento.visita):
                continue
            payload = {'titulo': row.titulo, 'solicitante': row.solicitante, 'sala': row.sala,
                       'sala_id': row.sala_id, 'sala_slug': row.sala_slug,
                       'inicio': row.inicio.isoformat(), 'fim': row.fim.isoformat(),
                       'quantidade_pessoas': row.quantidade_pessoas, 'status': row.status,
                       'criado_em': row.criado_em.isoformat()}
            created = link is None
            booking = Agendamento(visita=True, criado_por=None) if created else link.agendamento
            previous = {key: getattr(booking, key) for key in ('inicio', 'fim', 'quantidade_pessoas', 'situacao', 'cancelado_em')}
            previous_payload = link.payload if link is not None else None
            booking.inicio, booking.fim = row.inicio, row.fim
            booking.quantidade_pessoas = row.quantidade_pessoas
            booking.situacao = {'confirmada': 'confirmado', 'pendente': 'pendente',
                                'recusada': 'rejeitado', 'cancelada': 'confirmado'}[row.status]
            if row.status == 'confirmada':
                booking.cancelado_em = None
            elif row.status == 'cancelada' or ((created or link.recebida) and row.status != 'confirmada'):
                booking.cancelado_em = booking.cancelado_em or timezone.now()
            changed = created or any(getattr(booking, key) != value for key, value in previous.items())
            metadata_changed = link is not None and link.recebida and link.payload != payload
            if changed:
                booking.full_clean(exclude=['criado_por'])
                if not created:
                    booking.versao += 1
                booking.save()
            elif metadata_changed:
                booking.versao += 1
                booking.save(update_fields=['versao'])
            if created:
                Agendamento.objects.filter(pk=booking.pk).update(criado_em=row.criado_em)
                link = ReservaAgroHub(agendamento=booking, origem=origin, reserva_id=row.id, recebida=True)
                links[row.id] = link
            if link.recebida:
                link.payload = payload
            if created or changed or metadata_changed or link.status_remoto != row.status:
                link.status_remoto, link.estado = row.status, 'registrada'
                link.operacao, link.mensagem = 'atualizar', ''
                link.save()
            if created or changed or metadata_changed:
                EventoAgendamento.objects.create(
                    agendamento=booking, ator=None, ator_nome='AgroHub',
                    acao='criar' if created else 'cancelar' if booking.cancelado_em else 'editar',
                    alteracoes={'reserva_agrohub': {'anterior': previous_payload, 'novo': payload}},
                )
