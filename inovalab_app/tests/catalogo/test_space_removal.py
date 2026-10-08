from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class SpaceRemovalTests(TestCase):
    def test_space_model_table_and_route_names_are_removed(self):
        with self.assertRaises(LookupError):
            apps.get_model('catalogo', 'Espaco')
        self.assertNotIn('catalogo_espaco', connection.introspection.table_names())
        for name in ('catalogo:espacos-list', 'catalogo:espacos-create', 'catalogo_api:espaco-list'):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name)

    def test_old_space_routes_are_404_and_catalog_has_only_remaining_tabs(self):
        admin = get_user_model().objects.create_superuser('remocao-espacos')
        self.client.force_login(admin)
        for path in ('/catalogo/espacos/', '/catalogo/espacos/novo/', '/catalogo/espacos/1/',
                     '/catalogo/espacos/1/editar/', '/api/v1/espacos/', '/api/v1/espacos/1/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        self.assertRedirects(self.client.get('/catalogo/servicos/'), '/agenda/')
        response = self.client.get('/catalogo/equipamentos/')
        self.assertContains(response, 'Infraestrutura')
        self.assertNotContains(response, '/catalogo/servicos/')
        self.assertNotContains(response, '/catalogo/espacos/')
