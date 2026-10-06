from datetime import datetime, timedelta, timezone as utc_timezone

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.agrohub.client import AgroHubError, base_url
from accounts.agrohub.services import authenticated_request
from accounts.policies import is_business_admin
from agenda.models import Agendamento, ReservaAgroHub
from agenda.services import BookingConflict, _busy_as_conflict

SALA_ID = 1
REMOTE_STATUSES = {'pendente', 'confirmada', 'cancelada', 'recusada'}


def _marker(sync):
    return 'inovalab-visita:'+str(sync.referencia)


def queue_reservation(booking, actor, *, allow_create=False):
    sync = ReservaAgroHub.objects.select_for_update().filter(agendamento=booking).first()
    if sync is None:
        if not allow_create or not booking.visita or actor is None or actor.agrohub_id is None:
            return
        if booking.criado_por_id != actor.pk:
            raise PermissionDenied('A criação da reserva no AgroHub exige a sessão do criador da visita.')
        sync = ReservaAgroHub(agendamento=booking, origem=base_url())
    elif sync.estado in ('enviando', 'incerta'):
        raise BookingConflict('reserva_agrohub_inconclusiva', 'Confira o envio ao AgroHub antes de alterar esta visita.')
    if sync.origem != base_url():
        raise BookingConflict('origem_agrohub_alterada', 'A reserva pertence a outra origem do AgroHub. Confira a configuração.')
    if booking.cancelado_em or booking.situacao == 'rejeitado' or not booking.visita:
        sync.operacao = 'cancelar'
    else:
        sync.operacao = 'atualizar' if sync.reserva_id else 'criar'
        start, end = timezone.localtime(booking.inicio), timezone.localtime(booking.fim)
        if start.date() != end.date():
            raise BookingConflict('visita_agrohub_periodo', 'A visita deve começar e terminar no mesmo dia para reservar a sala no AgroHub.')
        sync.payload = {'titulo': 'Visita ao Laboratório InovaLab', 'quantidade_pessoas': 1,
            'data': start.date().isoformat(), 'hora_inicio': start.time().isoformat(), 'hora_fim': end.time().isoformat(),
            'observacoes': _marker(sync), 'status': 'pendente' if booking.situacao == 'pendente' else 'confirmada'}
    sync.estado, sync.mensagem = 'pendente', ''
    sync.save()


def can_sync(actor, sync):
    if actor is None or not actor.is_active or actor.agrohub_id is None:
        return False
    if sync.operacao == 'criar':
        return sync.agendamento.criado_por_id == actor.pk
    return is_business_admin(actor)


def _request(request, method, route, **kwargs):
    return authenticated_request(request, method, route, namespace='agendamentos', **kwargs)


def _pages(request, route, params):
    for page in range(1, 21):
        payload = _request(request, 'GET', route, params={**params, 'page': page, 'page_size': 100})
        rows, next_page = payload.get('results'), payload.get('next')
        if not isinstance(rows, list) or len(rows) > 100 or (next_page is not None and not isinstance(next_page, str)):
            raise AgroHubError()
        yield from rows
        if not next_page:
            return
    raise AgroHubError()


def _room(request):
    rooms = [row for row in _pages(request, 'salas/', {'site_code': 'inovalab'})
             if isinstance(row, dict) and type(row.get('id')) is int and row['id'] == SALA_ID]
    if len(rooms) != 1 or rooms[0].get('ativa') is not True or rooms[0].get('site_code') != 'inovalab':
        raise AgroHubError(400)
    slug = rooms[0].get('slug')
    if not isinstance(slug, str) or not slug or len(slug) > 200:
        raise AgroHubError(400)
    return slug


def _validate_remote(row, sync, *, period=False):
    if not isinstance(row, dict) or type(row.get('id')) is not int or not 0 < row['id'] <= 9223372036854775807:
        raise AgroHubError()
    room = row.get('sala')
    if (not isinstance(room, dict) or type(room.get('id')) is not int or room['id'] != SALA_ID
            or row.get('observacoes') != _marker(sync) or not isinstance(row.get('status'), str)
            or row['status'] not in REMOTE_STATUSES):
        raise AgroHubError()
    if period:
        try:
            for remote_name, local_name in (('inicio', 'hora_inicio'), ('fim', 'hora_fim')):
                remote = parse_datetime(row.get(remote_name, ''))
                expected = timezone.make_aware(datetime.fromisoformat(sync.payload['data']+'T'+sync.payload[local_name]))
                if remote is None or timezone.is_naive(remote) or remote.astimezone(utc_timezone.utc) != expected.astimezone(utc_timezone.utc):
                    raise AgroHubError()
        except (ValueError, TypeError):
            raise AgroHubError() from None
    return row


def _find(request, sync):
    rows = [row for row in _pages(request, 'reservas/', {'sala': sync.payload['sala'], 'data': sync.payload['data']})
            if isinstance(row, dict) and row.get('observacoes') == _marker(sync)]
    if len(rows) != 1:
        raise AgroHubError()
    return _validate_remote(rows[0], sync, period=True)


def reservation_summary(booking):
    sync = ReservaAgroHub.objects.filter(agendamento=booking).first()
    if sync is None:
        return None
    return {'reserva_id': sync.reserva_id, 'estado': sync.estado, 'status': sync.status_remoto,
            'mensagem': sync.mensagem}


def sync_after_change(request, booking):
    sync = ReservaAgroHub.objects.filter(agendamento=booking).first()
    # Uma criação rejeitada só é reenviada pela ação explícita do criador.
    # Administradores mantêm a aprovação local sem criar reservas em seu nome.
    if sync and can_sync(request.user, sync) and (sync.reserva_id is not None or sync.ultima_tentativa is None or sync.operacao == 'cancelar'):
        return sync_reservation(request, booking)
    return sync


def _maintain(request, sync, claim, progress, *, read_only=False):
    # Serializar a mutação enquanto o HTTP está em andamento. A intenção
    # já foi confirmada na transação local; este lock protege só o envio.
    # Um processo antigo não pode aplicar PATCH depois de uma nova edição.
    with transaction.atomic():
        if not claim.update(atualizado_em=F('atualizado_em')):
            return None
        remote = _request(request, 'GET', f'reservas/{sync.reserva_id}/')
        verified = _validate_remote(remote, sync)
        if verified['id'] != sync.reserva_id:
            raise AgroHubError()
        if read_only:
            return _validate_remote(remote, sync, period=sync.operacao != 'cancelar')
        if sync.operacao == 'cancelar':
            if verified['status'] != 'cancelada':
                progress['mutation'] = True
                _request(request, 'POST', f'reservas/{sync.reserva_id}/cancelar/', data={})
        else:
            progress['mutation'] = True
            _request(request, 'PATCH', f'reservas/{sync.reserva_id}/', data={key: value for key, value in sync.payload.items() if key != 'sala'})
        remote = _request(request, 'GET', f'reservas/{sync.reserva_id}/')
        verified = _validate_remote(remote, sync, period=sync.operacao != 'cancelar')
        if verified['id'] != sync.reserva_id:
            raise AgroHubError()
        return verified


@_busy_as_conflict
def sync_reservation(request, booking):
    with transaction.atomic():
        sync = ReservaAgroHub.objects.select_for_update().select_related('agendamento').filter(agendamento=booking).first()
        if sync is None or sync.estado == 'registrada':
            return sync
        if not can_sync(request.user, sync):
            raise PermissionDenied('Use a conta autorizada para enviar esta reserva ao AgroHub.')
        if sync.origem != base_url():
            raise BookingConflict('origem_agrohub_alterada', 'A reserva pertence a outra origem do AgroHub. Confira a configuração.')
        if sync.agendamento.versao != booking.versao:
            return sync
        uncertain = sync.estado == 'incerta'
        if sync.estado == 'enviando':
            if sync.ultima_tentativa and sync.ultima_tentativa > timezone.now()-timedelta(minutes=2):
                return sync
            uncertain = True
        # O slug é persistido antes de qualquer POST. Sem ele, o processo
        # anterior parou na consulta da sala e ainda não enviou a reserva.
        if sync.reserva_id is None and 'sala' not in sync.payload:
            uncertain = False
        claimed = ReservaAgroHub.objects.filter(pk=sync.pk, estado=sync.estado,
            ultima_tentativa=sync.ultima_tentativa).update(estado='enviando', ultima_tentativa=timezone.now(), atualizado_em=timezone.now())
        if not claimed:
            return sync
        sync.refresh_from_db()
    claim = ReservaAgroHub.objects.filter(pk=sync.pk, estado='enviando', ultima_tentativa=sync.ultima_tentativa)
    verified = None
    attempted_create = uncertain
    creation_accepted = False
    progress = {'mutation': False}
    try:
        if sync.operacao == 'cancelar' and sync.reserva_id is None:
            sync.status_remoto = ''
        else:
            if sync.reserva_id is None:
                if not uncertain:
                    sync.payload['sala'] = _room(request)
                    if not claim.update(payload=sync.payload, atualizado_em=timezone.now()):
                        return ReservaAgroHub.objects.get(pk=sync.pk)
                    attempted_create = True
                    returned = _request(request, 'POST', 'reservas/', data=sync.payload)
                    creation_accepted = True
                    if type(returned.get('id')) is int and returned['id'] > 0:
                        remote = _request(request, 'GET', f'reservas/{returned["id"]}/')
                        verified = _validate_remote(remote, sync, period=True)
                        if verified['id'] != returned['id']:
                            raise AgroHubError()
                    else:
                        verified = _find(request, sync)
                else:
                    verified = _find(request, sync)
                sync.reserva_id = verified['id']
            else:
                verified = _maintain(request, sync, claim, progress, read_only=uncertain)
                if verified is None:
                    return ReservaAgroHub.objects.get(pk=sync.pk)
            sync.status_remoto = verified['status']
            expected = 'cancelada' if sync.operacao == 'cancelar' else sync.payload['status']
            accepted = {expected}
            if sync.operacao == 'criar' and expected == 'pendente':
                accepted.add('confirmada')
            if sync.status_remoto not in accepted:
                raise AgroHubError(400)
        sync.estado, sync.mensagem = 'registrada', ''
    except AgroHubError as error:
        ambiguous = uncertain or (creation_accepted and sync.reserva_id is None) or (error.status >= 500 and (attempted_create or progress['mutation']))
        sync.estado = 'incerta' if ambiguous else 'falha'
        prefix = ('Não foi possível confirmar o resultado da reserva no AgroHub.' if sync.estado == 'incerta'
                  else 'A reserva não foi registrada no AgroHub.' if sync.operacao == 'criar' and sync.reserva_id is None
                  else 'A alteração ainda não foi confirmada no AgroHub.')
        sync.mensagem = prefix+(' Confira o resultado antes de reenviar.' if sync.estado == 'incerta' else ' Confira os dados e tente novamente.')
    claim.update(estado=sync.estado, mensagem=sync.mensagem, reserva_id=sync.reserva_id,
                 status_remoto=sync.status_remoto, atualizado_em=timezone.now())
    return ReservaAgroHub.objects.get(pk=sync.pk)
