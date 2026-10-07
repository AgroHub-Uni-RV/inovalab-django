import re
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.agrohub.client import AgroHubError
from accounts.agrohub.services import authenticated_request


@dataclass(frozen=True)
class PendingReservation:
    id: int
    sala: str
    titulo: str
    solicitante: str
    inicio: datetime
    fim: datetime
    quantidade_pessoas: int
    criado_em: datetime


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


def pending_reservations(request, *, query='', month=''):
    """Consulta somente leitura das reservas pendentes das salas InovaLab."""
    remaining_requests = 40

    def pages(route, params):
        nonlocal remaining_requests
        page = 1
        while remaining_requests:
            remaining_requests -= 1
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

    rooms = {}
    for room in pages('salas/', {'site_code': 'inovalab', 'ativas': 'false'}):
        if room.get('site_code') != 'inovalab':
            continue
        room_id, slug = room.get('id'), room.get('slug')
        if type(room_id) is not int or room_id < 1 or not isinstance(slug, str) or not re.fullmatch(r'[\w-]{1,220}', slug, re.ASCII):
            raise AgroHubError()
        rooms[room_id] = (slug, _text(room.get('nome'), 160))

    reservations = {}
    for room_id, (slug, name) in rooms.items():
        for row in pages('reservas/', {'sala': slug, 'status': 'pendente'}):
            room = row.get('sala')
            if (not isinstance(room, dict) or type(room.get('id')) is not int or room['id'] < 1
                    or not isinstance(room.get('slug'), str)
                    or row.get('status') not in ('pendente', 'confirmada', 'cancelada', 'recusada')):
                raise AgroHubError()
            if row['status'] != 'pendente' or room['id'] != room_id or room['slug'] != slug:
                continue
            pk, people = row.get('id'), row.get('quantidade_pessoas')
            if type(pk) is not int or not 0 < pk <= 9223372036854775807 or type(people) is not int or people < 1:
                raise AgroHubError()
            start, end = _instant(row.get('inicio')), _instant(row.get('fim'))
            if end <= start:
                raise AgroHubError()
            reservation = PendingReservation(
                id=pk, sala=name, titulo=_text(row.get('titulo'), 200),
                solicitante=_text(row.get('nome_solicitante'), 160, blank=True),
                inicio=start, fim=end, quantidade_pessoas=people, criado_em=_instant(row.get('created_at')),
            )
            if pk in reservations and reservations[pk] != reservation:
                raise AgroHubError()
            reservations[pk] = reservation

    rows = sorted(reservations.values(), key=lambda row: (row.criado_em, row.id), reverse=True)
    if month:
        rows = [row for row in rows if timezone.localtime(row.inicio).strftime('%Y-%m') == month]
    if query:
        query = query.casefold()
        rows = [row for row in rows if query in ' '.join((str(row.id), row.sala, row.titulo, row.solicitante)).casefold()]
    return rows
