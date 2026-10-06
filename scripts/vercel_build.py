"""Verifica produção e migra o Neon antes de publicar a aplicação."""
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


def main():
    # O script é chamado diretamente, com scripts/ no sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from django.core.exceptions import ImproperlyConfigured
    from setup.environment import read_database

    direct_url = os.environ.get('DATABASE_URL_UNPOOLED', '').strip()
    pooled_url = os.environ.get('DATABASE_URL', '').strip()
    if not direct_url or not pooled_url:
        raise ImproperlyConfigured('Configure DATABASE_URL e DATABASE_URL_UNPOOLED antes do build.')
    read_database(os.environ, Path.cwd())
    read_database({**os.environ, 'DATABASE_URL': direct_url}, Path.cwd())
    try:
        direct, pooled = urlsplit(direct_url), urlsplit(pooled_url)
        same_database = (
            direct.hostname == (pooled.hostname or '').replace('-pooler.', '.')
            and direct.path == pooled.path and direct.username == pooled.username
            and direct.port == pooled.port
        )
    except ValueError:
        raise ImproperlyConfigured('URLs de banco inválidas.') from None
    if '-pooler.' not in (pooled.hostname or ''):
        raise ImproperlyConfigured('DATABASE_URL deve usar pooler para o runtime da aplicação.')
    if not direct.hostname or '-pooler' in direct.hostname or not same_database:
        raise ImproperlyConfigured('As URLs devem usar o mesmo banco Neon; UNPOOLED deve ser direta.')

    # Só este processo usa a conexão direta. O runtime conserva o pool.
    os.environ['DATABASE_URL'] = direct_url
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection

    if settings.DEBUG:
        raise ImproperlyConfigured('O build exige DJANGO_DEBUG=false.')
    call_command('check', deploy=True, fail_level='WARNING')
    # Serializa migrações de builds concorrentes no mesmo banco. A conexão
    # direta conserva o advisory lock até concluir todas as migrações.
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '120s'")
            cursor.execute('SELECT pg_advisory_lock(%s)', [684726103])
        try:
            call_command('migrate', interactive=False)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [684726103])
    finally:
        connection.close()
    # O preset Django da Vercel executa collectstatic e publica na CDN.


if __name__ == '__main__':
    main()
