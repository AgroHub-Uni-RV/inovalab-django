from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from accounts.tests.test_identity import PASSWORD


class WebAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = get_user_model().objects.create_user(
            'ana', password=PASSWORD, first_name='Ana', last_name='Silva',
        )
        cls.admin = get_user_model().objects.create_superuser('admin', password=PASSWORD)

    def test_anonymous_home_redirects_to_login(self):
        self.assertRedirects(self.client.get('/perfil/'), '/?next=/perfil/', fetch_redirect_response=False)

    def test_login_and_private_home(self):
        self.assertRedirects(self.client.post('/entrar/', {
            'username': 'ana', 'password': PASSWORD,
        }), '/index/')
        self.assertContains(self.client.get('/perfil/'), 'ana')
        self.assertContains(self.client.get('/perfil/'), 'Ana Silva')

    def test_wrong_credentials_and_unknown_account_have_same_message(self):
        errors = []
        for username in ('ana', 'desconhecido'):
            response = self.client.post('/entrar/', {'username': username, 'password': 'errada'})
            self.assertEqual(response.status_code, 200)
            errors.append(list(response.context['form'].non_field_errors()))
            self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(errors[0])
        self.assertEqual(errors[0], errors[1])

    def test_inactive_account_cannot_login(self):
        self.ana.is_active = False
        self.ana.save(update_fields=['is_active'])
        response = self.client.post('/entrar/', {'username': 'ana', 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_local_next_is_honored(self):
        response = self.client.post('/entrar/', {
            'username': 'ana', 'password': PASSWORD, 'next': '/perfil/?origem=login',
        })
        self.assertRedirects(response, '/perfil/?origem=login')

    def test_external_next_is_rejected(self):
        for destination in ('https://externo.example/', '//externo.example/'):
            with self.subTest(destination=destination):
                response = self.client.post('/entrar/', {
                    'username': 'ana', 'password': PASSWORD, 'next': destination,
                })
                self.assertRedirects(response, '/index/')
                self.client.logout()

    def test_get_logout_does_not_end_session(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get('/sair/').status_code, 405)
        self.assertEqual(self.client.get('/perfil/').status_code, 200)

    def test_login_and_logout_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/entrar/')
        login = {'username': 'ana', 'password': PASSWORD}
        self.assertEqual(client.post('/entrar/', login).status_code, 403)
        self.assertNotIn('_auth_user_id', client.session)
        login['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        self.assertRedirects(client.post('/entrar/', login), '/index/')
        self.assertEqual(client.post('/sair/').status_code, 403)
        self.assertEqual(client.get('/perfil/').status_code, 200)
        self.assertRedirects(client.post('/sair/', {
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        }), '/')
        self.assertRedirects(client.get('/perfil/'), '/?next=/perfil/', fetch_redirect_response=False)

    def test_deactivation_revokes_existing_session(self):
        self.client.force_login(self.ana)
        self.ana.is_active = False
        self.ana.save(update_fields=['is_active'])
        self.assertRedirects(self.client.get('/perfil/'), '/?next=/perfil/', fetch_redirect_response=False)

    def test_business_admin_cannot_manage_accounts(self):
        self.ana.groups.add(Group.objects.get(name='Administradores'))
        self.client.force_login(self.ana)
        self.assertContains(self.client.get('/perfil/'), 'Administrador do laboratório')
        self.assertNotContains(self.client.get('/perfil/'), 'Administrar contas')
        self.assertEqual(self.client.get('/admin/accounts/user/').status_code, 302)

    def test_superuser_uses_sidebar_for_account_management(self):
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get('/perfil/'), 'Administrar contas')
        self.assertContains(self.client.get('/perfil/'), '/usuarios/')
        self.assertEqual(self.client.get('/admin/accounts/user/').status_code, 200)

    def test_login_fields_are_labeled_and_logout_form_is_post(self):
        response = self.client.get('/entrar/')
        self.assertContains(response, 'for="id_username"')
        self.assertContains(response, 'for="id_password"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.client.force_login(self.ana)
        self.assertContains(self.client.get('/perfil/'), 'action="/sair/" method="post"')
