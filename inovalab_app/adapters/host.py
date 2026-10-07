"""Small host boundary: domain code never imports the host's account model."""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

REQUIRED_METHODS = ('can_access_panel', 'is_business_admin', 'is_technical_admin',
                    'identity_context', 'has_profile_photo', 'profile_photo_response',
                    'load_events', 'send_contact')


class HostServiceError(Exception):
    def __init__(self, message='', *, status=None, errors=None):
        super().__init__(message)
        self.status = status
        self.errors = errors or {}


def get_adapter():
    path = getattr(settings, 'INOVALAB_HOST_ADAPTER', '')
    if not path:
        raise ImproperlyConfigured('Configure INOVALAB_HOST_ADAPTER.')
    adapter = import_string(path)()
    missing = [name for name in REQUIRED_METHODS if not callable(getattr(adapter, name, None))]
    if missing:
        raise ImproperlyConfigured('Adaptador InovaLab incompleto: '+', '.join(missing))
    return adapter


def can_access_panel(user):
    return get_adapter().can_access_panel(user)


def is_business_admin(user):
    return get_adapter().is_business_admin(user)


def is_technical_admin(user):
    return get_adapter().is_technical_admin(user)


def has_profile_photo(user):
    return get_adapter().has_profile_photo(user)


def profile_photo_response(user):
    return get_adapter().profile_photo_response(user)


def load_events():
    return get_adapter().load_events()


def send_contact(payload):
    return get_adapter().send_contact(payload)


def identity_context(request):
    return {'inovalab_identity': get_adapter().identity_context(request)}
