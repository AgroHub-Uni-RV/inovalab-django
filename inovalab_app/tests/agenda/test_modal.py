from inovalab_app.tests.agenda.helpers import service_web_data, make_booking
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from inovalab_app.agenda.models import AgendaEquipamento, AgendaServico, AgendaVisita, EventoAgendamento
from inovalab_app.catalogo.models import Equipamento, Servico


class BookingModalTests(TestCase):
    headers = {'HTTP_X_BOOKING_MODAL': '1'}

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('administrador-modal')
        cls.staff = get_user_model().objects.create_user('solicitante-modal', is_staff=True)
        cls.outside = get_user_model().objects.create_user('externo-modal')
        cls.service = Servico.objects.first()
        cls.machine = Equipamento.objects.create(nome='Máquina do modal')

    def setUp(self):
        self.client.force_login(self.admin)

    def payload(self, category):
        if category == 'visita':
            return {'categoria': category, 'quantidade_pessoas': '5', 'data': '2099-11-01',
                    'hora_inicio': '10:00', 'hora_termino': '11:00', 'observacoes': 'Visita no modal'}
        return service_web_data(titulo='Reserva no modal', prazo_hora='11:00')

    def test_modal_steps_return_only_fragment_and_do_not_save_on_navigation(self):
        for path in ('/agenda/novo/',
                     '/agenda/novo/?categoria=servico', '/agenda/visitas/novo/'):
            response = self.client.get(path, **self.headers)
            self.assertContains(response, 'data-booking-modal-content')
            self.assertNotContains(response, '<html')
            self.assertNotContains(response, 'id="booking-modal"')
            self.assertNotContains(response, 'id="sidebar"')
            self.assertIn('X-Booking-Modal', response['Vary'])
            self.assertEqual(response['Cache-Control'], 'no-store')
            if path != '/agenda/novo/':
                self.assertContains(response, 'data-booking-step')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertContains(response, 'action="/agenda/visitas/novo/"' if 'visitas/' in path
                                    else 'action="/agenda/novo/"')
        self.assertEqual(EventoAgendamento.objects.count(), 0)
        for model in (AgendaServico, AgendaEquipamento, AgendaVisita):
            self.assertFalse(model.objects.exists())

    def test_modal_confirmation_persists_each_category_and_returns_success_without_redirect(self):
        for category, model in (('servico', AgendaServico), ('visita', AgendaVisita)):
            with self.subTest(category=category):
                path = '/agenda/visitas/novo/' if category == 'visita' else '/agenda/novo/'
                invalid = self.client.post(path, self.payload(category) | ({'hora_termino': '09:00'} if category == 'visita' else {'titulo': ''}), **self.headers)
                self.assertContains(invalid, 'data-booking-modal-content')
                self.assertContains(invalid, 'errorlist')
                self.assertTrue(invalid.context['form'].errors)
                self.assertFalse(model.objects.exists())
                response = self.client.post(path, self.payload(category), **self.headers)
                self.assertEqual(response.status_code, 201)
                self.assertNotIn('Location', response)
                booking = model.objects.get()
                self.assertEqual(response.json(), {'created': True, 'message': 'Agendamento salvo.',
                                                  'detail_url': booking.get_absolute_url()})
                self.assertEqual((booking.criado_por, booking.eventos.count()), (self.admin, 1))

    def test_staff_submission_is_pending_and_conflict_keeps_form_values(self):
        self.client.force_login(self.staff)
        response = self.client.post('/agenda/visitas/novo/', self.payload('visita'), **self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(AgendaVisita.objects.get().situacao, 'pendente')
        self.assertIn('Aguarde a confirmação', response.json()['message'])
        self.client.force_login(self.admin)
        self.client.post('/agenda/visitas/novo/', self.payload('visita'), **self.headers)
        conflict = self.client.post('/agenda/visitas/novo/', self.payload('visita'), **self.headers)
        self.assertContains(conflict, 'data-booking-modal-content', status_code=409)
        self.assertEqual(conflict.context['form']['observacoes'].value(), 'Visita no modal')
        self.assertEqual(AgendaVisita.objects.count(), 2)
        self.assertEqual(EventoAgendamento.objects.count(), 2)

    def test_modal_allows_normal_users_but_requires_auth_csrf_and_rejects_spoofed_fields(self):
        self.client.logout()
        response = self.client.get('/agenda/novo/', **self.headers)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/entrar/', response.url)
        self.client.force_login(self.outside)
        self.assertEqual(self.client.get('/agenda/novo/', **self.headers).status_code, 200)
        response = self.client.post('/agenda/visitas/novo/', self.payload('visita'), **self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['detail_url'].startswith('/agenda/meus/'))
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post('/agenda/visitas/novo/', self.payload('visita'), **self.headers).status_code, 403)
        strict.get('/agenda/visitas/novo/', **self.headers)
        data = self.payload('visita') | {'csrfmiddlewaretoken': strict.cookies['csrftoken'].value,
                                       'criado_por': str(self.outside.pk)}
        invalid = strict.post('/agenda/visitas/novo/', data, **self.headers)
        self.assertTrue(invalid.context['form'].errors)
        data.pop('criado_por')
        data['data'] = '2099-11-02'
        self.assertEqual(strict.post('/agenda/visitas/novo/', data, **self.headers).status_code, 201)

    def test_single_modal_available_on_internal_pages_and_institutional_entry(self):
        for path in ('/agenda/', '/agenda/meus/', '/agenda/novo/', '/'):
            response = self.client.get(path)
            self.assertContains(response, 'id="booking-modal"', count=1)
            self.assertContains(response, 'inovalab_app/agenda/booking-modal.js', count=1)
        self.assertContains(self.client.get('/'), 'href="/agenda/meus/" class="inova-quicknav__item"')

    def test_editing_remains_on_existing_page_even_with_modal_header(self):
        booking = make_booking(actor=self.admin)
        response = self.client.get(f'/agenda/servico/{booking.pk}/editar/', **self.headers)
        self.assertNotContains(response, 'data-booking-modal-content')
        self.assertNotContains(response, 'data-booking-create-page')
        self.assertContains(response, '<html')
