import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


BASE_DIR = Path(__file__).resolve().parents[2]


class DeploymentGuardTests(TestCase):
    def run_build(self, values):
        environ = {key: value for key, value in os.environ.items() if not key.startswith((
            'DJANGO_', 'DATABASE_', 'VERCEL',
        ))}
        environ.update({
            'VERCEL': '1', 'DJANGO_DEBUG': 'false',
            'DJANGO_SECRET_KEY': 'test-only-' + 's' * 64,
            'DJANGO_ALLOWED_HOSTS': 'inovalab-test.vercel.app', **values,
        })
        return subprocess.run(
            [sys.executable, 'scripts/vercel_build.py'], cwd=BASE_DIR,
            env=environ, capture_output=True, text=True, timeout=15,
        )

    def test_missing_database_stops_before_migration(self):
        result = self.run_build({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Configure DATABASE_URL e DATABASE_URL_UNPOOLED', result.stderr)

    def test_mismatched_database_stops_without_exposing_password(self):
        result = self.run_build({
            'DATABASE_URL': 'postgresql://user:hidden-password@ep-a-pooler.neon.tech/app?sslmode=require',
            'DATABASE_URL_UNPOOLED': 'postgresql://user:hidden-password@ep-b.neon.tech/app?sslmode=require',
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('mesmo banco Neon', result.stderr)
        self.assertNotIn('hidden-password', result.stderr)

    def test_pooler_cannot_be_used_for_migrations(self):
        url = 'postgresql://user:hidden-password@ep-a-pooler.neon.tech/app?sslmode=require'
        result = self.run_build({'DATABASE_URL': url, 'DATABASE_URL_UNPOOLED': url})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('UNPOOLED deve ser direta', result.stderr)

    def test_runtime_url_must_use_pooler(self):
        url = 'postgresql://user:hidden-password@ep-a.neon.tech/app?sslmode=require'
        result = self.run_build({'DATABASE_URL': url, 'DATABASE_URL_UNPOOLED': url})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DATABASE_URL deve usar pooler', result.stderr)

    def test_production_security_headers_and_csrf(self):
        environ = dict(os.environ, VERCEL='1', DJANGO_DEBUG='false',
                       DJANGO_SECRET_KEY='test-only-' + 's' * 64,
                       DJANGO_ALLOWED_HOSTS='inovalab-test.vercel.app',
                       DATABASE_URL='postgresql://user:unused@ep-a-pooler.neon.tech/app?sslmode=require')
        code = '''
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'setup.settings'
import django
django.setup()
from django.core.management import call_command
call_command('check', deploy=True, fail_level='WARNING')
from django.test import Client
client = Client(enforce_csrf_checks=True)
redirect = client.get('/entrar/', HTTP_HOST='inovalab-test.vercel.app')
assert redirect.status_code == 301
response = client.get('/entrar/', HTTP_HOST='inovalab-test.vercel.app', HTTP_X_FORWARDED_PROTO='https')
assert response.status_code == 200
assert response['X-Frame-Options'] == 'DENY'
assert response['X-Content-Type-Options'] == 'nosniff'
assert 'max-age=31536000' in response['Strict-Transport-Security']
assert response.cookies['csrftoken']['secure']
assert client.get('/entrar/', HTTP_HOST='host-nao-autorizado.local', HTTP_X_FORWARDED_PROTO='https').status_code == 400
assert client.post('/entrar/', HTTP_HOST='inovalab-test.vercel.app', HTTP_X_FORWARDED_PROTO='https').status_code == 403
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=BASE_DIR,
                                env=environ, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
