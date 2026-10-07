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
    observacoes: str
    atualizado_em: datetime

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
    _linked(request)
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


def _room_catalog(request, budget):
    rooms = {}
    for room in _pages(request, 'salas/', {'site_code': 'inovalab', 'ativas': 'false'}, budget):
        if room.get('site_code') != 'inovalab':
            continue
        room_id, slug = room.get('id'), room.get('slug')
        if type(room_id) is not int or room_id < 1 or not isinstance(slug, str) or not re.fullmatch(r'[\w-]{1,220}', slug, re.ASCII):
            raise AgroHubError()
        _text(room.get('nome'), 160)
        if type(room.get('ativa')) is not bool:
            raise AgroHubError()
        if room_id in rooms and rooms[room_id] != room:
            raise AgroHubError()
        rooms[room_id] = room
    return rooms


def _rooms(request, budget):
    return {pk: (row['slug'], row['nome']) for pk, row in _room_catalog(request, budget).items()}


def available_rooms(request):
    return [(row['slug'], row['nome']) for row in _room_catalog(request, [40]).values() if row['ativa']]


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
        observacoes=_text(row.get('observacoes'), 512*1024, blank=True),
        atualizado_em=_instant(row.get('updated_at')),
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


def _linked(request):
    if request.user.agrohub_id is None:
        raise AgroHubError(401)


def _valid_id(reservation_id):
    if type(reservation_id) is not int or not 0 < reservation_id <= 9223372036854775807:
        raise AgroHubError(400)


def _validated_reservation(row, rooms, *, reservation_id=None, room_id=None, status=None):
    room = row.get('sala')
    if (not isinstance(room, dict) or type(room.get('id')) is not int
            or not isinstance(room.get('slug'), str) or not isinstance(row.get('status'), str)
            or row['status'] not in RESERVATION_STATUSES):
        raise AgroHubError()
    if room['id'] not in rooms or rooms[room['id']][0] != room['slug']:
        raise AgroHubError(403)
    if ((reservation_id is not None and (type(row.get('id')) is not int or row['id'] != reservation_id))
            or (room_id is not None and room['id'] != room_id)
            or (status is not None and row['status'] != status)):
        raise AgroHubError()
    return _reservation(row, room['id'], room['slug'], rooms[room['id']][1])


def get_reservation(request, reservation_id):
    """Lê um detalhe autorizado e valida a sala InovaLab, sem listar reservas."""
    _linked(request)
    _valid_id(reservation_id)
    route = f'reservas/{reservation_id}/'
    row = authenticated_request(request, 'GET', route, namespace='agendamentos')
    return _validated_reservation(row, _rooms(request, [40]), reservation_id=reservation_id)


def _mutation_result(result, original, *, status=None, preserve_fields=False):
    # A resposta precisa conservar o alvo validado antes do envio.
    remote = _validated_reservation(result, {original.sala_id: (original.sala_slug, original.sala)},
                                    reservation_id=original.id, room_id=original.sala_id, status=status)
    if preserve_fields and any(getattr(remote, field) != getattr(original, field) for field in
                               ('inicio', 'fim', 'titulo', 'quantidade_pessoas', 'observacoes', 'solicitante', 'criado_em')):
        raise AgroHubError()
    return remote


def save_reservation(request, data, *, reservation_id=None):
    """Cria/edita exclusivamente no provedor; status e sala editada não são enviados."""
    from agenda.remote_forms import RemoteVisitForm
    _linked(request)
    if not isinstance(data, dict):
        raise AgroHubError(400)
    fields = {'titulo', 'quantidade_pessoas', 'data', 'hora_inicio', 'hora_fim', 'observacoes'}
    if reservation_id is None:
        fields.add('sala')
    if (set(data) - fields or type(data.get('quantidade_pessoas')) is not int
            or any(not isinstance(data.get(field, ''), str) for field in fields - {'quantidade_pessoas'})):
        raise AgroHubError(400)
    original = get_reservation(request, reservation_id) if reservation_id is not None else None
    choices = available_rooms(request) if original is None else ()
    form = RemoteVisitForm(data, rooms=choices, booking=original)
    if not form.is_valid():
        raise AgroHubError(400)
    payload = form.payload()
    result = authenticated_request(request, 'PATCH' if original else 'POST',
                                   f'reservas/{reservation_id}/' if original else 'reservas/',
                                   namespace='agendamentos', data=payload)
    if original:
        remote = _mutation_result(result, original, status=original.status)
    else:
        rooms = {pk: value for pk, value in _rooms(request, [40]).items() if value[0] == payload['sala']}
        remote = _validated_reservation(result, rooms)
        if remote.status not in ('pendente', 'confirmada'):
            raise AgroHubError()
    start, end = timezone.localtime(remote.inicio), timezone.localtime(remote.fim)
    if (remote.titulo != payload['titulo'] or remote.quantidade_pessoas != payload['quantidade_pessoas']
            or remote.observacoes != payload['observacoes'] or start.date().isoformat() != payload['data']
            or start.strftime('%H:%M') != payload['hora_inicio'] or end.strftime('%H:%M') != payload['hora_fim']
            or start.second or start.microsecond or end.second or end.microsecond):
        raise AgroHubError()
    return remote


def cancel_reservation(request, reservation_id):
    original = get_reservation(request, reservation_id)
    if original.status not in ('pendente', 'confirmada') or original.inicio < timezone.now():
        raise AgroHubError(409)
    result = authenticated_request(request, 'POST', f'reservas/{reservation_id}/cancelar/',
                                   namespace='agendamentos', data={})
    return _mutation_result(result, original, status='cancelada', preserve_fields=True)


def decide_reservation(request, reservation_id, decision):
    """Aplica uma decisão somente a uma reserva pendente do InovaLab."""
    if decision not in ('confirmar', 'cancelar', 'recusar'):
        raise AgroHubError(400)
    original = get_reservation(request, reservation_id)
    if original.status != 'pendente':
        raise AgroHubError(409)
    if decision == 'cancelar':
        return cancel_reservation(request, reservation_id)
    expected_status = {'confirmar': 'confirmada', 'cancelar': 'cancelada', 'recusar': 'recusada'}[decision]
    result = authenticated_request(
        request, 'PATCH', f'reservas/{reservation_id}/', namespace='agendamentos',
        data={'status': expected_status},
    )
    return _mutation_result(result, original, status=expected_status, preserve_fields=True)
