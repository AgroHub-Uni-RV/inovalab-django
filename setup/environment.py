from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import dj_database_url

from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class RuntimeSettings:
    debug: bool
    secret_key: str
    allowed_hosts: tuple[str, ...]


def read_environment(environ: Mapping[str, str]) -> RuntimeSettings:
    on_vercel = environ.get('VERCEL') == '1'
    value = environ.get('DJANGO_DEBUG', 'false' if on_vercel else 'true').strip().casefold()
    if value not in ('true', '1', 'yes', 'on', 'false', '0', 'no', 'off'):
        raise ImproperlyConfigured('DJANGO_DEBUG deve informar true ou false.')
    debug = value in ('true', '1', 'yes', 'on')
    if on_vercel and debug:
        raise ImproperlyConfigured('DJANGO_DEBUG deve ser false na Vercel.')
    secret_key = environ.get('DJANGO_SECRET_KEY', '')
    if not secret_key.strip():
        if not debug:
            raise ImproperlyConfigured('Informe DJANGO_SECRET_KEY quando DJANGO_DEBUG=false.')
        secret_key = 'django-insecure-inovalab-local-development-only'
    hosts = environ.get('DJANGO_ALLOWED_HOSTS', '' if on_vercel else 'localhost,127.0.0.1')
    allowed_hosts = [host.strip() for host in hosts.split(',') if host.strip()]
    if on_vercel:
        for key in ('VERCEL_URL', 'VERCEL_BRANCH_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
            host = environ.get(key, '').strip()
            if host:
                allowed_hosts.append(host)
        if not allowed_hosts:
            raise ImproperlyConfigured('Informe DJANGO_ALLOWED_HOSTS na Vercel.')
    if not debug and any(host == '*' or host.startswith('.') for host in allowed_hosts):
        raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS deve listar hosts exatos em produção.')
    return RuntimeSettings(debug, secret_key, tuple(dict.fromkeys(allowed_hosts)))


def read_database(environ: Mapping[str, str], base_dir: Path) -> dict:
    url = environ.get('DATABASE_URL', '').strip()
    if not url:
        if environ.get('VERCEL') == '1':
            raise ImproperlyConfigured('Informe DATABASE_URL do Neon na Vercel.')
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': base_dir / 'db.sqlite3'}
    try:
        database = dj_database_url.parse(url, conn_max_age=0, conn_health_checks=True)
    except (ValueError, TypeError):
        raise ImproperlyConfigured('DATABASE_URL deve ser uma URL PostgreSQL válida.') from None
    if database['ENGINE'] != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('DATABASE_URL deve apontar para PostgreSQL.')
    permitted_options = {
        'sslmode', 'sslrootcert', 'sslcert', 'sslkey', 'channel_binding', 'connect_timeout',
    }
    if set(database.get('OPTIONS', {})) - permitted_options:
        raise ImproperlyConfigured('DATABASE_URL contém parâmetros de conexão não permitidos.')
    if environ.get('VERCEL') == '1' and database.get('OPTIONS', {}).get('sslmode') not in (
        'require', 'verify-ca', 'verify-full',
    ):
        raise ImproperlyConfigured('DATABASE_URL deve usar sslmode=require ou verificação de certificado.')
    # PgBouncer do Neon usa transaction pooling.
    database['DISABLE_SERVER_SIDE_CURSORS'] = True
    database.setdefault('OPTIONS', {}).setdefault('connect_timeout', 15)
    return database
