from inovalab_app.tests.agenda.helpers import make_service, make_booking
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
        booking = make_booking(actor=self.user)
        self.assertEqual(self.client.get(booking.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(reverse('agenda:creator-photo', args=['servico', booking.pk])).status_code, 404)

    @override_settings(LOGIN_URL='/laboratorio/entrar/?tenant=inovalab')
    def test_task_modal_exposes_its_prefixed_creation_and_login_routes(self):
        admin = get_user_model().objects.create_superuser('admin-modal-nativo', password='test-only')
        self.client.force_login(admin)
        response = self.client.get(reverse('tarefas:board'))
        self.assertContains(response, 'data-create-url="/laboratorio/tarefas/nova/"')
        self.assertContains(response, 'data-login-url="/laboratorio/entrar/?tenant=inovalab"')

    def test_clear_filters_keeps_host_prefix_and_clears_admin_month(self):
        from inovalab_app.tests.shared.test_clear_filters import ClearLinkParser
        admin = get_user_model().objects.create_superuser('admin-limpar-nativo')
        self.client.force_login(admin)
        response = self.client.get('/laboratorio/agenda/?q=pedido&mes=2099-01&categoria=servico&page=1')
        links = ClearLinkParser(response.content.decode()).links
        self.assertEqual(links, ['/laboratorio/agenda/?mes='])
        clean = self.client.get(links[0])
        self.assertEqual(clean.status_code, 200)
        self.assertEqual((clean.context['month'], clean.context['query'], clean.context['selected_category']), ('', '', ''))

    def test_task_board_movement_uses_prefixed_host_routes_and_native_identity(self):
        from inovalab_app.tarefas.services import save_task
        admin = get_user_model().objects.create_superuser('admin-movimento-nativo')
        booking = make_booking(actor=admin)
        task = save_task(actor=admin, data={'agendamento_servico': booking,
                         'responsavel': self.user, 'descricao': 'Mover com usuário nativo'})
        self.client.force_login(self.user)
        response = self.client.get(reverse('tarefas:board'))
        self.assertContains(response, f'data-api-url="/laboratorio/api/v1/tarefas/{task.pk}/transicoes/"')
        self.assertContains(response, f'action="/laboratorio/tarefas/{task.pk}/transicoes/"')
        moved = self.client.post(reverse('tarefa-transicoes', args=[task.pk]),
                                 {'status': 'criacao', 'versao': 1}, content_type='application/json')
        self.assertEqual(moved.status_code, 200)
        self.assertEqual((moved.json()['status'], moved.json()['versao']), ('criacao', 2))
