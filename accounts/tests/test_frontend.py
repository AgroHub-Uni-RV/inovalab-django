from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.tests.test_identity import PASSWORD
from accounts.tests.agrohub_stub import AccountsProviderMixin


class FrontendRoutesTests(AccountsProviderMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('frontend-user', password=PASSWORD)

    def test_login_is_at_entrar_and_index_requires_authentication(self):
        self.assertContains(self.client.get('/entrar/'), 'Entre na sua conta')
        self.assertRedirects(self.client.get('/index/'), '/entrar/?next=/index/', fetch_redirect_response=False)

    def test_login_default_and_authenticated_login_go_to_index(self):
        self.assertRedirects(self.client.post('/entrar/', {'username': self.user.username, 'password': PASSWORD}), '/index/')
        self.assertRedirects(self.client.get('/entrar/'), '/index/')
        self.assertContains(self.client.get('/perfil/'), 'Minha conta')

    def test_login_alias_and_safe_next(self):
        for destination, expected in [('/materiais/', '/materiais/'), ('https://externo.example', '/index/')]:
            self.client.logout()
            self.assertRedirects(self.client.post('/entrar/', {
                'username': self.user.username, 'password': PASSWORD, 'next': destination,
            }), expected)

    def test_shared_layout_menu_marks_current_module(self):
        self.client.force_login(self.user)
        for path in ('/index/', '/tarefas/', '/materiais/', '/catalogo/equipamentos/', '/perfil/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="sidebar"')
                self.assertContains(response, 'aria-current="page"')
                self.assertNotContains(response, '/usuarios/')
                self.assertNotContains(response, '/integracoes/')
        self.assertEqual(self.client.get('/painel/').status_code, 200)

    def test_login_self_returns_normalize_to_index(self):
        self.client.force_login(self.user)
        for path in ('/entrar/',):
            for destination in ('/entrar/', '/entrar/?next=/entrar/',
                                '?next=/entrar/', '#login', 'http://testserver/entrar/'):
                with self.subTest(path=path, destination=destination):
                    self.assertRedirects(self.client.get(path, {'next':destination}), '/index/',
                                         fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/entrar/', {'next':'/materiais/'}), '/materiais/', fetch_redirect_response=False)

    def test_login_post_self_return_normalizes_to_index(self):
        for destination in ('/entrar/', '/entrar/?next=/entrar/'):
            self.client.logout()
            self.assertRedirects(self.client.post('/entrar/', {'username':self.user.username,
                                'password':PASSWORD, 'next':destination}), '/index/')

    def test_catalog_menu_remains_current_for_all_categories(self):
        self.client.force_login(self.user)
        for path in ('/catalogo/equipamentos/',):
            response = self.client.get(path)
            selected = [item['label'] for item in response.context['nav_items'] if item['current']]
            self.assertEqual(selected, ['Infraestrutura'])

    def test_logout_returns_to_root_and_public_remains_public(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post('/sair/'), '/')
        response = self.client.get('/publico/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="sidebar"')
        self.assertNotContains(response, 'frontend-user')
