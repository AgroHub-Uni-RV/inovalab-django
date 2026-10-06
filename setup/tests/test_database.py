from pathlib import Path
from unittest import TestCase

from django.core.exceptions import ImproperlyConfigured

from setup.environment import read_database


class DatabaseSettingsTests(TestCase):
    def test_local_defaults_to_sqlite(self):
        self.assertEqual(read_database({}, Path('/app')), {
            'ENGINE': 'django.db.backends.sqlite3', 'NAME': Path('/app/db.sqlite3'),
        })

    def test_postgresql_preserves_ssl_and_escaped_credentials(self):
        database = read_database({
            'DATABASE_URL': 'postgresql://user:p%40ss@ep-test-pooler.neon.tech/db?sslmode=require',
        }, Path('/app'))
        self.assertEqual(database['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(database['PASSWORD'], 'p@ss')
        self.assertEqual(database['HOST'], 'ep-test-pooler.neon.tech')
        self.assertEqual(database['OPTIONS']['sslmode'], 'require')
        self.assertEqual(database['CONN_MAX_AGE'], 0)
        self.assertTrue(database['DISABLE_SERVER_SIDE_CURSORS'])

    def test_vercel_requires_database(self):
        with self.assertRaisesRegex(ImproperlyConfigured, 'DATABASE_URL'):
            read_database({'VERCEL': '1'}, Path('/app'))

    def test_local_postgres_without_query_parameters(self):
        database = read_database({'DATABASE_URL': 'postgresql://user:pass@localhost/app'}, Path('/app'))
        self.assertEqual(database['OPTIONS']['connect_timeout'], 15)

    def test_invalid_url_never_leaks_credentials(self):
        for url in ('mysql://user:secret@db/db', 'not-a-url', 'postgresql://user:secret@db:invalid/db'):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured) as error:
                read_database({'DATABASE_URL': url}, Path('/app'))
            self.assertNotIn('secret', str(error.exception))

    def test_vercel_requires_encrypted_postgres(self):
        for url in ('postgresql://user:secret@db/db', 'postgresql://user:secret@db/db?sslmode=disable'):
            with self.subTest(url=url), self.assertRaisesRegex(ImproperlyConfigured, 'sslmode'):
                read_database({'VERCEL': '1', 'DATABASE_URL': url}, Path('/app'))

    def test_query_parameters_cannot_redirect_connection(self):
        for option in ('dbname=other', 'host=other', 'user=other', 'service=other', 'options=-csearch_path=other'):
            with self.subTest(option=option), self.assertRaisesRegex(ImproperlyConfigured, 'parâmetros'):
                read_database({
                    'DATABASE_URL': 'postgresql://user:hidden-password@ep-a.neon.tech/app?sslmode=require&' + option,
                }, Path('/app'))
