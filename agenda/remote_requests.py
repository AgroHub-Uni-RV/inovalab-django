import re
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.agrohub.client import AgroHubError
from accounts.agrohub.services import authenticated_request


RESERVATION_STATUSES = {'pendente': 'Pendente', 'confirmada': 'Confirmada',
                        'cancelada': 'Cancelada', 'recusada': 'Recusada'}


@dataclass(frozen=True)
class RemoteReservation:
    id: int
    sala: str
    titulo: str
    solicitante: str
    inicio: datetime
    fim: datetime
    quantidade_pessoas: int
    criado_em: datetime
    status: str
    sala_id: int
    sala_slug: str

    categoria = 'visita'
    categoria_display = 'Visitas'
    cancelado_em = None
    motivo = ''
    recebido_agrohub = True

    @property
    def pk(self):
        return self.id

    @property
    def objeto_nome(self):
        return self.titulo

    @property
    def criador_nome(self):
        return self.solicitante or 'Não informado'

    @property
    def situacao(self):
        return {'confirmada': 'confirmado', 'recusada': 'rejeitado'}.get(self.status, self.status)

    def get_situacao_display(self):
        return self.status_label

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('agenda:visit-detail', kwargs={'pk': self.pk})

    @property
    def status_label(self):
        return RESERVATION_STATUSES[self.status]


def _text(value, maximum, *, blank=False):
    if not isinstance(value, str) or len(value) > maximum or (not blank and not value.strip()):
        raise AgroHubError()
    return value


def _instant(value):
    try:
        parsed = parse_datetime(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    if parsed is None or timezone.is_naive(parsed):
        raise AgroHubError()
    try:
        timezone.localtime(parsed)
    except (OverflowError, ValueError):
        raise AgroHubError() from None
    return parsed


def _pages(request, route, params, budget):
    page = 1
    while budget[0]:
        budget[0] -= 1
        payload = authenticated_request(request, 'GET', route, namespace='agendamentos',
                                        params={**params, 'page': page, 'page_size': 100})
        rows, next_page = payload.get('results'), payload.get('next')
        if (not isinstance(rows, list) or len(rows) > 100
                or (next_page is not None and not isinstance(next_page, str))):
            raise AgroHubError()
        for row in rows:
            if not isinstance(row, dict):
                raise AgroHubError()
            yield row
        if not next_page:
            return
        # Nunca seguir a URL next: preservar origem, filtros e Bearer da sessão.
        page += 1
    raise AgroHubError()


def _rooms(request, budget):
    rooms = {}
    for room in _pages(request, 'salas/', {'site_code': 'inovalab', 'ativas': 'false'}, budget):
        if room.get('site_code') != 'inovalab':
            continue
        room_id, slug = room.get('id'), room.get('slug')
        if type(room_id) is not int or room_id < 1 or not isinstance(slug, str) or not re.fullmatch(r'[\w-]{1,220}', slug, re.ASCII):
            raise AgroHubError()
        rooms[room_id] = (slug, _text(room.get('nome'), 160))
    return rooms


def _reservation(row, room_id, slug, name):
    pk, people = row.get('id'), row.get('quantidade_pessoas')
    if type(pk) is not int or not 0 < pk <= 9223372036854775807 or type(people) is not int or not 1 <= people <= 2147483647:
        raise AgroHubError()
    start, end = _instant(row.get('inicio')), _instant(row.get('fim'))
    if end <= start or timezone.localtime(start).date() != timezone.localtime(end).date():
        raise AgroHubError()
    return RemoteReservation(
        id=pk, sala=name, titulo=_text(row.get('titulo'), 200),
        solicitante=_text(row.get('nome_solicitante'), 160, blank=True),
        inicio=start, fim=end, quantidade_pessoas=people, criado_em=_instant(row.get('created_at')),
        status=row['status'], sala_id=room_id, sala_slug=slug,
    )


def reservations(request, *, query='', month=''):
    """Consulta todas as situações das reservas das salas InovaLab."""
    budget = [40]
    rooms = _rooms(request, budget)

    by_id = {}
    for room_id, (slug, name) in rooms.items():
        for row in _pages(request, 'reservas/', {'sala': slug}, budget):
            room = row.get('sala')
            if (not isinstance(room, dict) or type(room.get('id')) is not int or room['id'] < 1
                    or not isinstance(room.get('slug'), str)
                    or not isinstance(row.get('status'), str) or row['status'] not in RESERVATION_STATUSES):
                raise AgroHubError()
            if room['id'] != room_id or room['slug'] != slug:
                continue
            reservation = _reservation(row, room_id, slug, name)
            pk = reservation.id
            if pk in by_id and by_id[pk] != reservation:
                raise AgroHubError()
            by_id[pk] = reservation

    rows = sorted(by_id.values(), key=lambda row: (row.criado_em, row.id), reverse=True)
    if month:
        rows = [row for row in rows if timezone.localtime(row.inicio).strftime('%Y-%m') == month]
    if query:
        query = query.casefold()
        rows = [row for row in rows if query in ' '.join((str(row.id), row.sala, row.titulo, row.solicitante)).casefold()]
    return rows


def decide_reservation(request, reservation_id, decision):
    """Aplica uma decisão somente a uma reserva pendente do InovaLab."""
    if (decision not in ('confirmar', 'cancelar', 'recusar') or type(reservation_id) is not int
            or not 0 < reservation_id <= 9223372036854775807):
        raise AgroHubError(400)
    route = f'reservas/{reservation_id}/'
    row = authenticated_request(request, 'GET', route, namespace='agendamentos')
    room = row.get('sala')
    if (type(row.get('id')) is not int or row['id'] != reservation_id
            or not isinstance(room, dict) or type(room.get('id')) is not int
            or not isinstance(room.get('slug'), str)):
        raise AgroHubError()
    rooms = _rooms(request, [40])
    if room['id'] not in rooms or rooms[room['id']][0] != room['slug']:
        raise AgroHubError(403)
    if not isinstance(row.get('status'), str) or row['status'] not in RESERVATION_STATUSES:
        raise AgroHubError()
    if row['status'] != 'pendente':
        raise AgroHubError(409)
    expected_status = {'confirmar': 'confirmada', 'cancelar': 'cancelada', 'recusar': 'recusada'}[decision]
    result = authenticated_request(
        request, 'POST' if decision == 'cancelar' else 'PATCH',
        route+'cancelar/' if decision == 'cancelar' else route, namespace='agendamentos',
        data={} if decision == 'cancelar' else {'status': expected_status},
    )
    updated_room = result.get('sala')
    if (type(result.get('id')) is not int or result['id'] != reservation_id
            or result.get('status') != expected_status or not isinstance(updated_room, dict)
            or type(updated_room.get('id')) is not int or updated_room['id'] != room['id']
            or updated_room.get('slug') != room['slug']):
        raise AgroHubError()
    return _reservation(result, room['id'], room['slug'], rooms[room['id']][1])
