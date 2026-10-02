from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from integracoes.credentials import CredentialRejected, authenticate_token


class IntegrationAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if len(parts) != 2 or parts[0].lower() != b'bearer':
            raise AuthenticationFailed('Informe uma credencial Bearer válida.')
        try:
            principal = authenticate_token(parts[1].decode('ascii'))
        except (CredentialRejected, UnicodeDecodeError) as error:
            raise AuthenticationFailed('Credencial de integração inválida ou revogada.') from error
        return principal, principal

    def authenticate_header(self, request):
        return 'Bearer realm="integracoes"'
