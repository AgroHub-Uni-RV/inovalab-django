from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import Resolver404, resolve


class RemovedIntegrationsTests(TestCase):
    def test_retired_web_and_api_routes_are_not_registered(self):
        for path in ('/integracoes/', '/integracoes/novo/', '/integracoes/1/',
                     '/integracoes/1/editar/', '/integracoes/1/credencial/',
                     '/integracoes/1/pedidos/', '/api/v1/integracoes/catalogo/',
                     '/api/v1/integracoes/agendamentos/'):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)

    def test_admin_sidebar_has_no_integrations_and_remaining_modules_render(self):
        user = get_user_model().objects.create_superuser('admin-sem-integracoes')
        self.client.force_login(user)
        with patch('inovalab_app.shared.views.load_events', return_value=([], False)):
            for path in ('/index/', '/agenda/', '/materiais/', '/tarefas/',
                         '/banners/', '/catalogo/servicos/', '/perfil/'):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, '/integracoes/')
                    self.assertNotContains(response, '>Integrações<')

    def test_integrations_app_is_not_installed(self):
        self.assertFalse(apps.is_installed('integracoes'))
