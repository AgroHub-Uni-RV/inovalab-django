from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from inovalab_app.models import AgendaServico, Servico


class NativeHostTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('equipe-nativa', is_staff=True)

    def test_registry_and_database_use_only_the_host_identity(self):
        self.assertFalse(apps.is_installed('accounts'))
        self.assertEqual(get_user_model()._meta.label, 'auth.User')
        self.assertFalse(hasattr(self.user, 'agrohub_roles'))
        self.assertNotIn('accounts_user', connection.introspection.table_names())
        self.assertEqual(AgendaServico._meta.get_field('criado_por').related_model, get_user_model())

    @override_settings(LOGIN_URL='/entrar/?tenant=inovalab')
    def test_login_query_keeps_return_path_under_prefix(self):
        target = reverse('core:dashboard') + '?mes=10'
        response = self.client.get(target)
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlsplit(response.url).query)
        self.assertEqual(query['tenant'], ['inovalab'])
        self.assertEqual(query['next'], [target])

    def test_pages_render_and_navigation_respects_the_prefix(self):
        self.client.force_login(self.user)
        for name in ('core:dashboard', 'agenda:list', 'tarefas:board', 'materiais:list', 'conteudo:inicio'):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '/laboratorio/agenda/')
                self.assertNotContains(response, '/perfil/')
                self.assertNotContains(response, 'action=""')
        response = self.client.get(reverse('agenda:list'))
        self.assertTrue(next(item for item in response.context['nav_items'] if item['label'] == 'Agendamentos')['current'])

    def test_normal_user_can_create_a_personal_visit_but_cannot_list_internal_api(self):
        ordinary = get_user_model().objects.create_user('visitante-nativo')
        self.client.force_login(ordinary)
        self.assertEqual(self.client.get('/laboratorio/api/v1/agendamentos/').status_code, 403)
        self.assertEqual(self.client.get(reverse('agenda:create')).status_code, 200)
        response = self.client.post('/laboratorio/api/v1/agendamentos/', {
            'categoria': 'visita', 'quantidade_pessoas': 2,
            'data': (timezone.localdate()+timedelta(days=5)).isoformat(),
            'hora_inicio': '09:00', 'hora_termino': '10:00', 'observacoes': 'Nativo',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)

    def test_public_api_remains_public_and_admin_api_remains_restricted(self):
        self.assertEqual(self.client.get('/laboratorio/api/v1/publico/banners/?local=home').status_code, 200)
        self.assertEqual(self.client.get('/laboratorio/api/v1/banners/').status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('conteudo:list')).status_code, 403)
        admin = get_user_model().objects.create_superuser('admin-nativo', password='test-only')
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse('conteudo:list')).status_code, 200)

    def test_creator_photo_is_optional_for_native_users(self):
        self.client.force_login(self.user)
        booking = AgendaServico.objects.create(servico=Servico.objects.first(), criado_por=self.user, motivo='Teste',
                                               inicio=timezone.now(), fim=timezone.now()+timedelta(hours=1))
        self.assertEqual(self.client.get(booking.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(reverse('agenda:creator-photo', args=['servico', booking.pk])).status_code, 404)
