from inovalab_app.tests.agenda.helpers import service_data, service_web_data
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase
from rest_framework.test import APIClient

from inovalab_app.agenda.models import BOOKING_MODELS
from inovalab_app.agenda.services import BookingConflict, cancel_booking, review_booking, save_booking
from inovalab_app.catalogo.models import Equipamento, Servico


class NormalBookingAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('agendador-normal')
        cls.other = get_user_model().objects.create_user('outro-agendador')
        cls.admin = get_user_model().objects.create_superuser('admin-agendador')
        cls.equipment = Equipamento.objects.create(nome='Máquina para usuários')
        cls.service = Servico.objects.first()

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, category):
        if category == 'visita':
            return {'quantidade_pessoas': '3', 'data': '2099-12-10',
                    'hora_inicio': '09:00', 'hora_termino': '10:00', 'observacoes': 'Visita própria'}
        return service_web_data(prazo_data='2099-12-10', prazo_hora='10:00', titulo='Pedido próprio')

    def create(self, category, *, actor=None):
        data = self.payload(category)
        data['categoria'] = category
        if category == 'visita':
            data.update(quantidade_pessoas=3, data=datetime(2099, 12, 10).date(),
                        hora_inicio=datetime(2099, 12, 10, 9).time(), hora_termino=datetime(2099, 12, 10, 10).time())
        else:
            data = service_data(prazo=datetime.fromisoformat('2099-12-10T10:00:00-03:00'), titulo='Pedido próprio')
        return save_booking(actor=actor or self.user, data=data)

    def test_active_normal_user_can_create_all_categories_in_modal_and_read_own_result(self):
        response = self.client.get('/agenda/meus/')
        self.assertContains(response, 'Novo agendamento')
        self.assertContains(response, 'data-page-content')
        for category, model in [(category, model) for category, model in BOOKING_MODELS.items() if category != 'equipamento']:
            with self.subTest(category=category):
                url = '/agenda/visitas/novo/' if category == 'visita' else '/agenda/novo/'
                fragment = self.client.get(url, {'categoria': category}, HTTP_X_BOOKING_MODAL='1')
                self.assertEqual(fragment.status_code, 200)
                response = self.client.post(url, self.payload(category), HTTP_X_BOOKING_MODAL='1')
                self.assertEqual(response.status_code, 201, response.content)
                booking = model.objects.get()
                self.assertEqual((booking.criado_por_id, booking.situacao, booking.versao), (self.user.pk, 'pendente', 1))
                self.assertContains(self.client.get(response.json()['detail_url']), 'Cancelar agendamento')
                self.assertEqual(booking.eventos.get().ator_id, self.user.pk)

    def test_creation_without_javascript_uses_public_layout_and_personal_redirect(self):
        for category in ('servico', 'visita'):
            with self.subTest(category=category):
                url = '/agenda/visitas/novo/' if category == 'visita' else '/agenda/novo/'
                page = self.client.get(url, {'categoria': category})
                self.assertNotContains(page, 'id="sidebar"')
                self.assertContains(page, 'Meus agendamentos')
                response = self.client.post(url, self.payload(category))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/agenda/meus/'))
                self.assertEqual(self.client.get(response.url).status_code, 200)

    def test_owner_cancels_each_category_with_version_and_history_preserved(self):
        for category in ('servico', 'visita'):
            with self.subTest(category=category):
                booking = self.create(category)
                url = f'/agenda/meus/{category}/{booking.pk}/cancelar/'
                self.assertContains(self.client.get(url), 'Confirmar cancelamento')
                booking.refresh_from_db()
                self.assertIsNone(booking.cancelado_em)
                self.assertRedirects(self.client.post(url, {'versao': 1}), '/agenda/meus/')
                booking.refresh_from_db()
                self.assertIsNotNone(booking.cancelado_em)
                self.assertEqual(booking.versao, 2)
                event = booking.eventos.get(acao='cancelar')
                self.assertEqual(event.ator_id, self.user.pk)
                detail = self.client.get(f'/agenda/meus/{category}/{booking.pk}/')
                self.assertContains(detail, 'Cancelado em')
                self.assertNotContains(detail, 'Confirmar cancelamento')
                self.assertNotContains(detail, 'Cancelar agendamento')
                self.assertEqual(self.client.post(url, {'versao': 2}).status_code, 404)

    def test_other_owners_cannot_cancel_in_web_api_or_service_even_with_matching_ids(self):
        api = APIClient()
        api.force_login(self.other)
        self.client.force_login(self.other)
        for category in ('servico', 'visita'):
            with self.subTest(category=category):
                booking = self.create(category)
                url = f'/agenda/meus/{category}/{booking.pk}/cancelar/'
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {'versao': 1}).status_code, 404)
                self.assertEqual(api.delete(f'/api/v1/agendamentos/{category}/{booking.pk}/', {'versao': 1}, format='json').status_code, 404)
                with self.assertRaises(PermissionDenied):
                    cancel_booking(actor=self.other, category=category, booking_id=booking.pk, expected_version=1)
                booking.refresh_from_db()
                self.assertIsNone(booking.cancelado_em)
                self.assertEqual(booking.eventos.count(), 1)

    def test_stale_missing_or_spoofed_cancel_data_does_not_mutate_own_booking(self):
        booking = self.create('visita')
        url = f'/agenda/meus/visita/{booking.pk}/cancelar/'
        for data, status in (({'versao': 2}, 409), ({}, 400), ({'versao': 1, 'criado_por': self.other.pk}, 400)):
            self.assertEqual(self.client.post(url, data).status_code, status)
        booking.refresh_from_db()
        self.assertEqual((booking.versao, booking.cancelado_em, booking.eventos.count()), (1, None, 1))

    def test_normal_user_api_creation_and_own_cancellation_keep_other_api_actions_protected(self):
        api = APIClient()
        api.force_login(self.user)
        for category in ('servico', 'visita'):
            data = self.payload(category)
            if category == 'visita':
                data['quantidade_pessoas'] = 3
            if category == 'servico':
                data = service_data(prazo='2099-12-10T10:00:00-03:00')
            data['categoria'] = category
            created = api.post('/api/v1/agendamentos/', data, format='json')
            self.assertEqual(created.status_code, 201, created.content)
            url = f'/api/v1/agendamentos/{category}/{created.json()["id"]}/'
            self.assertEqual(api.patch(url, {'versao': 1}, format='json').status_code, 403)
            self.assertEqual(api.delete(url, {'versao': 1}, format='json').status_code, 204)
        for url in ('/agenda/', '/agenda/solicitacoes/', '/catalogo/servicos/', '/tarefas/', '/materiais/', '/api/v1/agendamentos/'):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_can_cancel_another_users_booking_and_owner_cannot_edit_or_approve(self):
        for category in ('servico', 'visita'):
            booking = self.create(category)
            with self.assertRaises(PermissionDenied):
                save_booking(actor=self.user, category=category, booking_id=booking.pk, expected_version=1, data={})
            with self.assertRaises(PermissionDenied):
                review_booking(actor=self.user, category=category, booking_id=booking.pk, expected_version=1, decision='aprovar')
            review_booking(actor=self.admin, category=category, booking_id=booking.pk, expected_version=1, decision='aprovar',
                task_data={'descricao': 'Executar serviço', 'responsaveis': [self.user]})
            cancel_booking(actor=self.admin, category=category, booking_id=booking.pk, expected_version=2)
            booking.refresh_from_db()
            self.assertIsNotNone(booking.cancelado_em)

    def test_confirmed_booking_owner_can_cancel_and_free_confirmed_slot(self):
        booking = self.create('visita')
        review_booking(actor=self.admin, category='visita', booking_id=booking.pk, expected_version=1, decision='aprovar')
        with self.assertRaises(BookingConflict):
            self.create('visita', actor=self.admin)
        cancel_booking(actor=self.user, category='visita', booking_id=booking.pk, expected_version=2)
        self.assertEqual(self.create('visita', actor=self.admin).situacao, 'confirmado')

    def test_csrf_anonymous_and_inactive_accounts_cannot_create_or_cancel(self):
        booking = self.create('visita')
        url = f'/agenda/meus/visita/{booking.pk}/cancelar/'
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(url, {'versao': 1}).status_code, 403)
        self.assertEqual(strict.post('/agenda/visitas/novo/', self.payload('visita')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(url, {'versao': 1}).status_code, 302)
        self.assertEqual(self.client.get('/agenda/novo/').status_code, 302)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        for operation in (lambda: self.create('visita'), lambda: cancel_booking(actor=self.user, category='visita', booking_id=booking.pk, expected_version=1)):
            with self.assertRaises(PermissionDenied):
                operation()

    def test_equipment_photos_for_creation_require_login_and_never_allow_file_traversal(self):
        url = '/catalogo/equipamentos/foto/'
        for name in ('inexistente.png', '../../AGENTS.md'):
            self.assertEqual(self.client.get(url, {'arquivo': name}).status_code, 404)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_admin_cannot_cancel_pending_or_rejected_even_when_the_booking_is_their_own(self):
        api = APIClient()
        api.force_login(self.admin)
        self.client.force_login(self.admin)
        for category, model in [(category, model) for category, model in BOOKING_MODELS.items() if category != 'equipamento']:
            for status in ('pendente', 'rejeitado'):
                for owner in (self.user, self.admin):
                    with self.subTest(category=category, status=status, owner=owner.username):
                        booking = self.create(category)
                        model.objects.filter(pk=booking.pk).update(situacao=status, criado_por=owner)
                        booking.refresh_from_db()
                        url = f'/agenda/{category}/{booking.pk}/'
                        self.assertNotContains(self.client.get(url), 'Cancelar agendamento')
                        self.assertEqual(self.client.get(url + 'cancelar/').status_code, 403)
                        self.assertEqual(self.client.post(url + 'cancelar/', {'versao': 1}).status_code, 403)
                        if owner == self.admin:
                            personal_url = f'/agenda/meus/{category}/{booking.pk}/'
                            self.assertNotContains(self.client.get(personal_url), 'Cancelar agendamento')
                            self.assertEqual(self.client.get(personal_url + 'cancelar/').status_code, 403)
                            self.assertEqual(self.client.post(personal_url + 'cancelar/', {'versao': 1}).status_code, 403)
                        response = api.delete(f'/api/v1/agendamentos/{category}/{booking.pk}/', {'versao': 1}, format='json')
                        self.assertEqual(response.status_code, 403)
                        self.assertIn('confirmados', response.json()['detail'])
                        with self.assertRaisesMessage(PermissionDenied, 'somente agendamentos confirmados'):
                            cancel_booking(actor=self.admin, category=category, booking_id=booking.pk, expected_version=1)
                        booking.refresh_from_db()
                        self.assertEqual((booking.versao, booking.cancelado_em, booking.eventos.count()), (1, None, 1))

    def test_requests_offer_admin_cancel_only_for_confirmed_cards(self):
        bookings = []
        for category, model in [(category, model) for category, model in BOOKING_MODELS.items() if category != 'equipamento']:
            for status in ('pendente', 'rejeitado', 'confirmado'):
                booking = self.create(category)
                model.objects.filter(pk=booking.pk).update(situacao=status)
                bookings.append((booking, status))
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/')
        for booking, status in bookings:
            url = f'/agenda/{booking.categoria}/{booking.pk}/cancelar/'
            if status == 'confirmado':
                self.assertContains(response, url)
                self.assertContains(self.client.get(booking.get_absolute_url()), 'Cancelar agendamento')
                self.assertRedirects(self.client.post(url, {'versao': 1}), '/agenda/solicitacoes/')
                booking.refresh_from_db()
                self.assertEqual(booking.versao, 2)
                self.assertIsNotNone(booking.cancelado_em)
            else:
                self.assertNotContains(response, url)
