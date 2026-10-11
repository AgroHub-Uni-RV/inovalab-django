from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase


class AdminShortcutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user('atalhos-admin')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.staff = User.objects.create_user('atalhos-equipe', is_staff=True)
        cls.external = User.objects.create_user('atalhos-externo')

    def setUp(self):
        self.enterContext(patch('inovalab_app.shared.views.load_events', return_value=([], False)))

    def test_active_business_admin_sees_shortcuts_across_panel_and_full_form_destinations(self):
        self.client.force_login(self.admin)
        for path in ('/index/', '/tarefas/', '/agenda/', '/materiais/', '/banners/',
                     '/catalogo/equipamentos/', '/perfil/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, 'aria-label="Criação rápida"', count=1)
                self.assertContains(response, 'href="/tarefas/nova/" data-task-modal-trigger aria-label="Criar tarefa"')
                self.assertContains(response, 'href="/agenda/novo/" aria-label="Criar agendamento"')
        for path in ('/tarefas/nova/', '/agenda/novo/'):
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_shortcuts_are_absent_for_staff_external_accounts_and_public_pages(self):
        for user, paths in ((self.staff, ('/index/', '/tarefas/', '/agenda/', '/perfil/')),
                            (self.external, ('/perfil/', '/agenda/meus/')),
                            (self.admin, ('/servicos/',))):
            self.client.force_login(user)
            for path in paths:
                with self.subTest(user=user.username, path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, 'aria-label="Criação rápida"')
                    self.assertNotContains(response, 'has-admin-shortcuts')
