import hashlib
import json
import secrets
from collections.abc import Mapping
from datetime import datetime, timezone as dt_timezone

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.policies import is_business_admin
from agenda.services import BASE_FIELDS, CATEGORY_MODELS, BookingConflict, _busy_as_conflict, _save_booking
from integracoes.credentials import CredentialRejected, IntegrationPrincipal, issue_token
from integracoes.models import ClienteIntegracao, PedidoIntegracao


REQUEST_FIELDS = BASE_FIELDS | {'id_externo', 'requerente_id', 'requerente'}


def _require_admin(actor):
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem gerenciar integrações.')


def _check_version(client, version):
    if type(version) is not int or version < 1:
        raise ValidationError({'versao': 'Informe a versão inteira positiva do integrador.'})
    if client.versao != version:
        raise BookingConflict('versao_desatualizada', 'O integrador foi alterado. Atualize antes de tentar novamente.')


def _locked_client(client_id):
    if not ClienteIntegracao.objects.filter(pk=client_id).update(ativo=F('ativo')):
        raise Http404
    return ClienteIntegracao.objects.get(pk=client_id)


@_busy_as_conflict
def create_client(*, actor, name):
    _require_admin(actor)
    if not isinstance(name, str):
        raise ValidationError({'nome': 'Informe o nome do sistema.'})
    client = ClienteIntegracao(nome=name.strip(), criado_por=actor)
    token = issue_token(client)
    client.full_clean()
    try:
        with transaction.atomic():
            client.save()
    except IntegrityError:
        if ClienteIntegracao.objects.filter(nome=client.nome).exists():
            raise ValidationError({'nome': 'Já existe um integrador com este nome.'})
        raise
    return client, token


@_busy_as_conflict
def update_client(*, actor, client_id, data, expected_version):
    _require_admin(actor)
    if set(data) - {'nome', 'ativo'}:
        raise ValidationError('Foram enviados campos que não podem ser alterados.')
    if 'ativo' in data and type(data['ativo']) is not bool:
        raise ValidationError({'ativo': 'Informe verdadeiro ou falso.'})
    if 'nome' in data and not isinstance(data['nome'], str):
        raise ValidationError({'nome': 'Informe o nome do sistema.'})
    with transaction.atomic():
        client = _locked_client(client_id)
        _check_version(client, expected_version)
        for name, value in data.items():
            setattr(client, name, value)
        if not client.ativo:
            client.token_digest = ''
        client.versao += 1
        client.full_clean()
        client.save(update_fields=['nome', 'ativo', 'token_digest', 'versao'])
    return client


@_busy_as_conflict
def rotate_credential(*, actor, client_id, expected_version):
    _require_admin(actor)
    with transaction.atomic():
        client = _locked_client(client_id)
        _check_version(client, expected_version)
        if not client.ativo:
            raise ValidationError({'ativo': 'Ative o integrador antes de gerar uma credencial.'})
        token = issue_token(client)
        client.versao += 1
        client.save(update_fields=['token_digest', 'versao'])
    return client, token


def normalize_request(data):
    if not isinstance(data, Mapping):
        raise ValidationError('Informe um objeto JSON.')
    errors = {name: 'Este campo não pode ser alterado.' for name in set(data) - REQUEST_FIELDS}
    errors.update({name: 'Este campo é obrigatório.' for name in REQUEST_FIELDS - set(data)})
    if errors:
        raise ValidationError(errors)
    normalized = dict(data)
    for name in ('id_externo', 'requerente_id', 'requerente', 'motivo'):
        value = data[name]
        if not isinstance(value, str) or not value.strip() or (name != 'motivo' and len(value.strip()) > 150):
            errors[name] = 'Informe texto não vazio' + (' com até 150 caracteres.' if name != 'motivo' else '.')
        else:
            normalized[name] = value.strip()
    if not isinstance(data['categoria'], str) or data['categoria'] not in CATEGORY_MODELS:
        errors['categoria'] = 'Selecione uma categoria válida.'
    if type(data['objeto']) is not int or data['objeto'] < 1:
        errors['objeto'] = 'Informe um ID inteiro positivo.'
    for name in ('inicio', 'fim'):
        value = data[name]
        if not isinstance(value, datetime) or timezone.is_naive(value):
            errors[name] = 'Informe data e hora com fuso horário.'
        else:
            normalized[name] = value.astimezone(dt_timezone.utc)
    if not errors and normalized['fim'] <= normalized['inicio']:
        errors['fim'] = 'O término deve ser posterior ao início.'
    if errors:
        raise ValidationError(errors)
    return normalized


@_busy_as_conflict
def receive_booking(*, principal, data):
    if not isinstance(principal, IntegrationPrincipal):
        raise CredentialRejected('É necessária uma credencial de integração válida.')
    normalized = normalize_request(data)
    canonical = {name: value.isoformat() if isinstance(value, datetime) else value for name, value in normalized.items()}
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
    with transaction.atomic():
        try:
            client = _locked_client(principal.cliente_id)
        except Http404 as error:
            raise CredentialRejected('Credencial revogada.') from error
        if not client.ativo or not client.token_digest or not secrets.compare_digest(client.token_digest, principal.token_digest):
            raise CredentialRejected('Credencial revogada.')
        receipt = PedidoIntegracao.objects.select_related('agendamento').filter(
            cliente=client, id_externo=normalized['id_externo'],
        ).first()
        if receipt:
            if receipt.conteudo_digest != digest:
                raise BookingConflict('idempotencia_conflitante', 'Este pedido externo já foi recebido com conteúdo diferente.')
            return receipt.agendamento, receipt, True
        booking = _save_booking(actor=None, actor_name=f'Integração: {client.nome}',
                                data={name: normalized[name] for name in BASE_FIELDS})
        receipt = PedidoIntegracao.objects.create(cliente=client, id_externo=normalized['id_externo'],
            requerente_id=normalized['requerente_id'], conteudo_digest=digest, agendamento=booking)
    return booking, receipt, False
