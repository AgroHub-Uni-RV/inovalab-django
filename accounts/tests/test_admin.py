from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from accounts.tests.test_identity import PASSWORD


class AccountAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin', password=PASSWORD)
        cls.user = get_user_model().objects.create_user('ana', password=PASSWORD)

    def test_admin_creates_active_user_with_hashed_password(self):
        self.client.force_login(self.admin)
        response = self.client.post('/admin/accounts/user/add/', {
            'username': 'nova', 'usable_password': 'true',
            'password1': PASSWORD, 'password2': PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username='nova')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_admin_rejects_weak_password(self):
        self.client.force_login(self.admin)
        response = self.client.post('/admin/accounts/user/add/', {
            'username': 'nova', 'usable_password': 'true',
            'password1': '123', 'password2': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='nova').exists())
        self.assertTrue(response.context['adminform'].form.errors)

    def test_admin_edits_and_deactivates_account(self):
        self.client.force_login(self.admin)
        response = self.client.post(f'/admin/accounts/user/{self.user.pk}/change/', {
            'username': 'ana', 'first_name': 'Ana', 'last_name': 'Silva',
            'email': 'ana@example.test', 'password': self.user.password,
            'date_joined_0': '2026-10-01', 'date_joined_1': '10:00:00',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Ana Silva')
        self.assertEqual(self.user.email, 'ana@example.test')
        self.assertFalse(self.user.is_active)

    def test_staff_permissions_cannot_manage_accounts_or_groups(self):
        staff = get_user_model().objects.create_user('staff', password=PASSWORD, is_staff=True)
        staff.user_permissions.add(*Permission.objects.filter(
            content_type__app_label__in=('accounts', 'auth'),
            codename__in=('add_user', 'change_user', 'view_user', 'delete_user',
                          'add_group', 'change_group', 'view_group', 'delete_group'),
        ))
        self.client.force_login(staff)
        group = Group.objects.get(name='Administradores')
        for path in ('/admin/accounts/user/', '/admin/accounts/user/add/',
                     f'/admin/accounts/user/{self.user.pk}/change/',
                     '/admin/auth/group/', '/admin/auth/group/add/',
                     f'/admin/auth/group/{group.pk}/change/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post('/admin/accounts/user/add/', {
            'username': 'intruso', 'usable_password': 'true',
            'password1': PASSWORD, 'password2': PASSWORD, 'is_superuser': 'on',
        }).status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username='intruso').exists())
        self.assertEqual(self.client.post(f'/admin/auth/group/{group.pk}/change/', {
            'name': 'Alterado',
        }).status_code, 403)
        group.refresh_from_db()
        self.assertEqual(group.name, 'Administradores')

    def test_superuser_can_manage_groups(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post('/admin/auth/group/add/', {
            'name': 'Teste',
        }).status_code, 302)
        self.assertTrue(Group.objects.filter(name='Teste').exists())
