import hashlib
import re
import secrets
from dataclasses import dataclass

from integracoes.models import ClienteIntegracao


class CredentialRejected(Exception):
    pass


@dataclass(frozen=True)
class IntegrationPrincipal:
    cliente_id: int
    token_digest: str
    is_authenticated: bool = True


def token_digest(token):
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def issue_token(client):
    token = f'inovalab_{client.identificador.hex}.{secrets.token_urlsafe(32)}'
    client.token_digest = token_digest(token)
    return token


def authenticate_token(token):
    match = re.fullmatch(r'inovalab_([0-9a-f]{32})\.[A-Za-z0-9_-]{43}', token) if isinstance(token, str) else None
    if match:
        client = ClienteIntegracao.objects.filter(identificador=match[1], ativo=True).first()
        digest = token_digest(token)
        if client and client.token_digest and secrets.compare_digest(client.token_digest, digest):
            return IntegrationPrincipal(client.pk, digest)
    raise CredentialRejected('Credencial de integração ausente, inválida ou revogada.')
