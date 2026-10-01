from collections.abc import Mapping
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class RuntimeSettings:
    debug: bool
    secret_key: str
    allowed_hosts: tuple[str, ...]


def read_environment(environ: Mapping[str, str]) -> RuntimeSettings:
    value = environ.get('DJANGO_DEBUG', 'true').strip().casefold()
    if value not in ('true', '1', 'yes', 'on', 'false', '0', 'no', 'off'):
        raise ImproperlyConfigured('DJANGO_DEBUG deve informar true ou false.')
    debug = value in ('true', '1', 'yes', 'on')
    secret_key = environ.get('DJANGO_SECRET_KEY', '')
    if not secret_key.strip():
        if not debug:
            raise ImproperlyConfigured('Informe DJANGO_SECRET_KEY quando DJANGO_DEBUG=false.')
        secret_key = 'django-insecure-inovalab-local-development-only'
    hosts = environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
    return RuntimeSettings(debug, secret_key, tuple(
        host.strip() for host in hosts.split(',') if host.strip()
    ))
