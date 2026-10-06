from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from accounts.tests.test_identity import PASSWORD


class IdentityApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = get_user_model().objects.create_user(
            'ana', password=PASSWORD, first_name='Ana', last_name='Silva',
        )
        cls.bruno = get_user_model().objects.create_user('bruno', password=PASSWORD)

    def test_anonymous_receives_403_without_identity(self):
        response = self.client.get('/api/v1/me/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(set(response.json()), {'detail'})

    def test_returns_only_current_user_and_exact_fields(self):
        self.client.force_login(self.ana)
        response = self.client.get(f'/api/v1/me/?id={self.bruno.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'id': self.ana.pk, 'username': 'ana', 'first_name': 'Ana',
            'last_name': 'Silva', 'is_business_admin': False,
        })

    def test_role_uses_group_or_superuser_not_staff(self):
        self.ana.is_staff = True
        self.ana.save(update_fields=['is_staff'])
        self.client.force_login(self.ana)
        self.assertFalse(self.client.get('/api/v1/me/').json()['is_business_admin'])
        self.ana.groups.add(Group.objects.get(name='Administradores'))
        self.assertTrue(self.client.get('/api/v1/me/').json()['is_business_admin'])
        self.ana.groups.clear()
        self.ana.is_superuser = True
        self.ana.save(update_fields=['is_superuser'])
        self.assertTrue(self.client.get('/api/v1/me/').json()['is_business_admin'])

    def test_authenticated_writes_with_csrf_return_405(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.ana)
        client.get('/perfil/')
        token = client.cookies['csrftoken'].value
        for method in ('post', 'put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(client, method)(
                    '/api/v1/me/', data='{}', content_type='application/json', HTTP_X_CSRFTOKEN=token,
                )
                self.assertEqual(response.status_code, 405)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.username, 'ana')

    def test_anonymous_writes_are_forbidden(self):
        for method in ('post', 'put', 'patch', 'delete'):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)('/api/v1/me/').status_code, 403)

    def test_deactivation_revokes_existing_api_session(self):
        self.client.force_login(self.ana)
        self.ana.is_active = False
        self.ana.save(update_fields=['is_active'])
        response = self.client.get('/api/v1/me/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(set(response.json()), {'detail'})

    def test_valid_logout_revokes_api_access(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.ana)
        client.get('/perfil/')
        self.assertEqual(client.get('/api/v1/me/').status_code, 200)
        client.post('/sair/', {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(client.get('/api/v1/me/').status_code, 403)
