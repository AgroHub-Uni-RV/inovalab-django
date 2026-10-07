from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase


class UserPageTests(TestCase):
    def setUp(self):
        self.enterContext(patch('core.views.load_events', return_value=([], False)))

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser('tecnico')
        cls.common = User.objects.create_user('interno', first_name='<script>nome</script>')
        cls.staff = User.objects.create_user('staff', is_staff=True)
        cls.business = User.objects.create_user('laboratorio')
        cls.business.groups.add(Group.objects.get(name='Administradores'))
        cls.inactive = User.objects.create_user('inativo', is_active=False)

    def test_agrohub_roles_override_local_flags_in_admin_counts_filter_and_labels(self):
        User = get_user_model()
        remote_admin = User.objects.create_user('admin-remoto', agrohub_id=42, agrohub_roles=['staff', 'admin'])
        remote_staff = User.objects.create_user('equipe-remota', agrohub_id=43, agrohub_roles=['staff'], is_superuser=True)
        remote_staff.groups.add(Group.objects.get(name='Administradores'))
        self.client.force_login(self.admin)
        response = self.client.get('/usuarios/?tab=administradores')
        self.assertEqual(response.context['user_counts']['administradores'], 3)
        self.assertContains(response, remote_admin.username)
        self.assertNotContains(response, remote_staff.username)
        response = self.client.get('/usuarios/?q=admin-remoto')
        self.assertContains(response, 'Administrador')

    def test_users_are_exclusive_to_active_technical_admin(self):
        self.assertRedirects(self.client.get('/usuarios/'), '/entrar/?next=/usuarios/', fetch_redirect_response=False)
        self.staff.user_permissions.add(Permission.objects.get(codename='view_user'))
        for actor in (self.common, self.staff, self.business):
            self.client.force_login(actor)
            self.assertEqual(self.client.get('/usuarios/').status_code, 403)
            self.assertNotContains(self.client.get('/perfil/'), '/usuarios/')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/usuarios/').status_code, 200)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/usuarios/').status_code, 302)

    def test_admin_links_go_to_reference_user_page(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/perfil/'), 'href="/usuarios/"')
        self.assertContains(self.client.get('/index/'), 'href="/usuarios/"')
        response = self.client.get('/usuarios/')
        self.assertContains(response, 'Configurar usuários')
        self.assertContains(response, '/admin/accounts/user/')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.post('/usuarios/').status_code, 405)

    def test_counts_and_tabs_use_actual_roles_and_status(self):
        self.client.force_login(self.admin)
        response = self.client.get('/usuarios/')
        self.assertEqual(response.context['user_counts'], {'total': 5, 'administradores': 2, 'ativos': 4, 'inativos': 1})
        for tab, names in [('administradores', {'tecnico', 'laboratorio'}), ('inativos', {'inativo'})]:
            response = self.client.get('/usuarios/', {'tab': tab})
            self.assertEqual({u.username for u in response.context['object_list']}, names)
        self.assertEqual(self.client.get('/usuarios/?tab=visitantes').context['selected_tab'], 'todos')

    def test_search_and_names_are_escaped_without_fictional_profiles(self):
        self.client.force_login(self.admin)
        response = self.client.get('/usuarios/', {'q': '<script>nome</script>'})
        self.assertEqual([u.pk for u in response.context['object_list']], [self.common.pk])
        self.assertContains(response, '&lt;script&gt;nome&lt;/script&gt;')
        self.assertNotContains(response, '<script>nome</script>')
        self.assertNotContains(response, 'Professor Técnico')

    def test_pagination_preserves_search_and_tab(self):
        get_user_model().objects.bulk_create([get_user_model()(username=f'busca-{i:02}') for i in range(16)])
        self.client.force_login(self.admin)
        response = self.client.get('/usuarios/', {'q': 'busca-', 'tab': 'ativos'})
        self.assertEqual(len(response.context['object_list']), 15)
        self.assertContains(response, 'q=busca-')
        self.assertContains(response, 'tab=ativos')
        self.assertEqual(len(self.client.get('/usuarios/?q=busca-&tab=ativos&page=2').context['object_list']), 1)
