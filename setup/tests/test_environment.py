from unittest import TestCase

from django.core.exceptions import ImproperlyConfigured

from setup.environment import read_environment


class EnvironmentTests(TestCase):
    def test_local_defaults(self):
        result = read_environment({})
        self.assertTrue(result.debug)
        self.assertEqual(result.allowed_hosts, ('localhost', '127.0.0.1'))
        self.assertTrue(result.secret_key.startswith('django-insecure-'))

    def test_boolean_values(self):
        for value in ('true', '1', 'yes', 'on', 'TRUE'):
            with self.subTest(value=value):
                self.assertTrue(read_environment({'DJANGO_DEBUG': value}).debug)
        for value in ('false', '0', 'no', 'off', 'FALSE'):
            with self.subTest(value=value):
                self.assertFalse(read_environment({
                    'DJANGO_DEBUG': value, 'DJANGO_SECRET_KEY': 'private-key',
                }).debug)

    def test_invalid_debug_is_rejected(self):
        with self.assertRaisesRegex(ImproperlyConfigured, 'DJANGO_DEBUG'):
            read_environment({'DJANGO_DEBUG': 'talvez'})

    def test_production_requires_secret(self):
        for value in (None, '', '   '):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ImproperlyConfigured, 'DJANGO_SECRET_KEY'):
                    environ = {'DJANGO_DEBUG': 'false'}
                    if value is not None:
                        environ['DJANGO_SECRET_KEY'] = value
                    read_environment(environ)

    def test_supplied_key_and_hosts(self):
        result = read_environment({
            'DJANGO_DEBUG': 'false', 'DJANGO_SECRET_KEY': 'private-key',
            'DJANGO_ALLOWED_HOSTS': ' exemplo.local, , localhost ',
        })
        self.assertEqual(result.secret_key, 'private-key')
        self.assertEqual(result.allowed_hosts, ('exemplo.local', 'localhost'))

    def test_vercel_defaults_to_production_and_requires_secret(self):
        with self.assertRaisesRegex(ImproperlyConfigured, 'DJANGO_SECRET_KEY'):
            read_environment({'VERCEL': '1'})

    def test_vercel_uses_exact_deployment_hosts(self):
        result = read_environment({
            'VERCEL': '1', 'DJANGO_SECRET_KEY': 'private-key',
            'DJANGO_ALLOWED_HOSTS': 'inovalab-test.vercel.app',
            'VERCEL_URL': 'inovalab-test-abc.vercel.app',
            'VERCEL_BRANCH_URL': 'inovalab-test-git-feature.vercel.app',
            'VERCEL_PROJECT_PRODUCTION_URL': 'inovalab-test.vercel.app',
        })
        self.assertFalse(result.debug)
        self.assertEqual(result.allowed_hosts, (
            'inovalab-test.vercel.app', 'inovalab-test-abc.vercel.app',
            'inovalab-test-git-feature.vercel.app',
        ))

    def test_vercel_rejects_debug_and_missing_hosts(self):
        for values in ({'DJANGO_DEBUG': 'true'}, {}):
            with self.subTest(values=values), self.assertRaises(ImproperlyConfigured):
                read_environment({
                    'VERCEL': '1', 'DJANGO_SECRET_KEY': 'private-key', **values,
                })

    def test_production_rejects_wildcard_hosts(self):
        with self.assertRaisesRegex(ImproperlyConfigured, 'DJANGO_ALLOWED_HOSTS'):
            read_environment({
                'DJANGO_DEBUG': 'false', 'DJANGO_SECRET_KEY': 'private-key',
                'DJANGO_ALLOWED_HOSTS': '*',
            })
