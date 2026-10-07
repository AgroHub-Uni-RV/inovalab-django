from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from accounts.policies import is_business_admin
from accounts.tests.agrohub_stub import AccountsStub, PASSWORD
from catalogo.models import Servico


class AgroHubRolesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stub = AccountsStub()
        cls.provider_settings = override_settings(AGROHUB_API_BASE_URL=cls.stub.url, DEBUG=True)
        cls.provider_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.provider_settings.disable()
        cls.stub.close()
        super().tearDownClass()

    def setUp(self):
        self.stub.reset()
        self.enterContext(patch('core.views.load_events', return_value=([], False)))
        self.enterContext(patch('conteudo.public_events.load_events', return_value=([], False)))

    def login(self, roles, **extra):
        self.stub.state['profile']['roles'] = roles
        # Flags não documentadas e profile.user_type não são fonte de autorização.
        self.stub.state['profile']['is_superuser'] = True
        return self.client.post('/entrar/', {'username': 'agro-ana', 'password': PASSWORD, **extra})

    def test_agrohub_admin_is_business_admin_without_global_django_privileges(self):
        response = self.login(['admin'])
        self.assertRedirects(response, '/index/')
        user = get_user_model().objects.get(agrohub_id=42)
        self.assertTrue(is_business_admin(user))
        self.assertFalse(user.is_superuser)
        self.assertEqual(self.client.get('/catalogo/servicos/novo/').status_code, 200)
        self.assertEqual(self.client.get('/integracoes/').status_code, 200)

    def test_staff_is_internal_user_and_cannot_use_administrative_functions(self):
        self.assertRedirects(self.login(['staff']), '/index/')
        user = get_user_model().objects.get(agrohub_id=42)
        self.assertFalse(is_business_admin(user))
        for path in ('/index/', '/painel/', '/agenda/', '/agenda/novo/', '/tarefas/', '/materiais/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get('/catalogo/servicos/novo/').status_code, 403)
        self.assertEqual(self.client.get('/integracoes/').status_code, 403)

    def test_regular_user_login_returns_home_and_all_internal_routes_are_forbidden(self):
        self.assertRedirects(self.login(['student'], next='/agenda/novo/'), '/')
        for path in ('/index/', '/painel/', '/agenda/', '/agenda/novo/', '/catalogo/servicos/',
                     '/tarefas/', '/materiais/', '/banners/', '/integracoes/', '/usuarios/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, 'id="sidebar"', status_code=403)
        for path in ('/api/v1/agendamentos/', '/api/v1/servicos/', '/api/v1/tarefas/',
                     '/api/v1/materiais/', '/api/v1/banners/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(set(response.json()), {'detail'})

    def test_regular_user_cannot_write_to_internal_api(self):
        self.login([])
        response = self.client.post('/api/v1/servicos/', {'nome': 'Não autorizado'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Servico.objects.filter(nome='Não autorizado').exists())

    def test_regular_user_keeps_own_profile_and_public_pages_without_internal_navigation(self):
        self.login(['partner'])
        for path in ('/', '/sobre/', '/regimento/', '/calendario-de-funcionamento/', '/perfil/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'id="sidebar"')
                self.assertNotContains(response, '>Área interna</a>')
        self.assertEqual(self.client.post('/perfil/', {'first_name': 'Beatriz', 'last_name': '',
                                                      'cpf': '', 'telefone': ''}).status_code, 302)
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 200)

    def test_role_revocation_immediately_removes_access_despite_local_privileges(self):
        self.login(['admin'])
        user = get_user_model().objects.get(agrohub_id=42)
        user.groups.add(Group.objects.get(name='Administradores'))
        user.is_staff = user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
        self.stub.state['profile']['roles'] = ['student']
        self.assertEqual(self.client.get('/index/').status_code, 403)
        user.refresh_from_db()
        self.assertFalse(is_business_admin(user))
        self.assertEqual(self.client.get('/api/v1/servicos/').status_code, 403)

    def test_role_change_from_staff_to_admin_is_applied_without_new_login(self):
        self.login(['staff'])
        self.assertEqual(self.client.get('/integracoes/').status_code, 403)
        self.stub.state['profile']['roles'] = ['admin']
        self.assertEqual(self.client.get('/integracoes/').status_code, 200)

    def test_staff_cannot_use_stale_technical_flags_to_manage_accounts_or_view_other_photos(self):
        self.login(['staff'])
        user = get_user_model().objects.get(agrohub_id=42)
        user.is_staff = user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
        other = get_user_model().objects.create_user('outro')
        for path in ('/usuarios/', '/admin/accounts/user/', '/admin/auth/group/',
                     f'/usuarios/{other.pk}/foto/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_missing_malformed_or_unknown_roles_never_grant_access(self):
        for roles in (None, 'admin', {}, ['Admin'], ['professor'], [True], [['admin']]):
            with self.subTest(roles=roles):
                self.client.logout()
                self.stub.reset()
                self.login(roles)
                self.assertNotEqual(self.client.get('/index/').status_code, 200)
        self.client.logout()
        self.stub.reset()
        del self.stub.state['profile']['roles']
        response = self.client.post('/entrar/', {'username': 'agro-ana', 'password': PASSWORD})
        self.assertNotEqual(self.client.get('/index/').status_code, 200)

    def test_profile_type_does_not_promote_user_to_team(self):
        self.stub.state['profile']['profile'] = {'user_type': 'admin'}
        self.login([])
        self.assertEqual(self.client.get('/index/').status_code, 403)

    def test_api_outage_denies_internal_access_and_keeps_public_pages_available(self):
        self.login(['admin'])
        self.stub.state['responses'][('GET', '/api/v1/accounts/me/')] = (503, {})
        self.assertEqual(self.client.get('/index/').status_code, 503)
        self.assertEqual(self.client.get('/api/v1/servicos/').status_code, 503)
        self.assertEqual(self.client.get('/regimento/').status_code, 200)

    def test_public_banner_api_remains_available_to_regular_users(self):
        self.login([])
        self.assertEqual(self.client.get('/api/v1/publico/banners/?local=home').status_code, 200)
