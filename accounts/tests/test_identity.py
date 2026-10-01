from importlib import import_module

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.db import connection
from django.test import TestCase
from django.apps import apps

from accounts.policies import is_business_admin


PASSWORD = 'InovaLab-Teste-2026!'


class IdentityTests(TestCase):
    def test_custom_user_and_default_flags(self):
        user = get_user_model().objects.create_user('ana', password=PASSWORD)
        self.assertEqual(user._meta.label, 'accounts.User')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_user_password_is_hashed(self):
        user = get_user_model().objects.create_user('ana', password=PASSWORD)
        user.refresh_from_db()
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_group_migration_is_idempotent(self):
        migration = import_module('accounts.migrations.0002_administrator_group')
        editor = connection.schema_editor()
        migration.create_administrator_group(apps, editor)
        migration.create_administrator_group(apps, editor)
        self.assertEqual(Group.objects.filter(name='Administradores').count(), 1)

    def test_anonymous_and_regular_user_are_not_business_admins(self):
        self.assertFalse(is_business_admin(AnonymousUser()))
        user = get_user_model().objects.create_user('ana', password=PASSWORD)
        self.assertFalse(is_business_admin(user))

    def test_staff_is_not_a_business_role(self):
        user = get_user_model().objects.create_user('staff', password=PASSWORD, is_staff=True)
        self.assertFalse(is_business_admin(user))
        user.groups.add(Group.objects.get(name='Administradores'))
        self.assertTrue(is_business_admin(user))
        user.is_active = False
        self.assertFalse(is_business_admin(user))

    def test_active_superuser_is_business_admin(self):
        user = get_user_model().objects.create_superuser('admin', password=PASSWORD)
        self.assertTrue(is_business_admin(user))
        user.is_active = False
        self.assertFalse(is_business_admin(user))
