"""Optional native-Django host; production still uses the AgroHub adapter."""
from django.conf import settings
from django.http import Http404
from django.shortcuts import resolve_url
from inovalab_app.adapters.host import HostServiceError


class DjangoHostAdapter:
    def can_access_panel(self, user):
        return bool(user and user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser))

    def is_business_admin(self, user):
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)

    is_technical_admin = is_business_admin

    def identity_context(self, request):
        return {
            'login_url': resolve_url(settings.LOGIN_URL),
            'logout_url': self._url('INOVALAB_LOGOUT_URL'),
            'profile_url': self._url('INOVALAB_PROFILE_URL'),
            'users_url': '', 'photo_url': '',
        }

    def _url(self, name):
        value = getattr(settings, name, '')
        return resolve_url(value) if value else ''

    def has_profile_photo(self, user):
        return False

    def profile_photo_response(self, user):
        raise Http404

    def load_events(self):
        return [], False

    def send_contact(self, payload):
        raise HostServiceError('Contato não configurado pelo hospedeiro.', status=503)
