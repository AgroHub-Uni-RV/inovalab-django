from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

from accounts.agrohub.client import AgroHubClient, AgroHubError
from accounts.agrohub.services import begin_session


class AgroHubBackend(ModelBackend):
    """Mantém permissões locais; toda autenticação de senha é remota."""

    @sensitive_variables('password', 'payload')
    def authenticate(self, request, username=None, password=None, **kwargs):
        if request is None or not username or not password:
            return None
        try:
            payload = AgroHubClient().request('POST', 'login/', data={'username': username, 'password': password})
            return begin_session(request, payload)
        except AgroHubError as error:
            if error.status in (400, 401, 403):
                return None
            raise ValidationError('O AgroHub está indisponível. Tente entrar novamente em instantes.') from None
