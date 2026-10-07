from django.urls import reverse
from accounts import policies
from accounts.agrohub.client import AgroHubClient, AgroHubError
from accounts.photos import profile_photo_response
from inovalab_app.adapters.host import HostServiceError


class AgroHubHostAdapter:
    can_access_panel = staticmethod(policies.can_access_panel)
    is_business_admin = staticmethod(policies.is_business_admin)
    is_technical_admin = staticmethod(policies.is_technical_admin)
    profile_photo_response = staticmethod(profile_photo_response)

    def has_profile_photo(self, user):
        return bool(user and getattr(user, 'tem_foto', False))

    def identity_context(self, request):
        user = request.user
        return {
            'login_url': reverse('accounts:login'),
            'logout_url': reverse('accounts:logout'),
            'profile_url': reverse('accounts:home'),
            'users_url': reverse('accounts:users') if policies.is_technical_admin(user) else '',
            'photo_url': reverse('accounts:photo', args=[user.pk]) if self.has_profile_photo(user) else '',
        }

    def load_events(self):
        from accounts.agrohub.events import load_events
        return load_events()

    def send_contact(self, payload):
        try:
            return AgroHubClient().request('POST', '', namespace='contact', data=payload)
        except AgroHubError as error:
            raise HostServiceError(str(error), status=error.status, errors=error.errors) from error
