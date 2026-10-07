from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIClient

from accounts.tests.agrohub_stub import AccountsStub, PASSWORD
from agenda.models import AgendaVisita, AgendaServico, EventoAgendamento
from agenda.services import BookingConflict, cancel_booking, review_booking, save_booking
from agenda.visit_forms import VisitForm
from catalogo.models import Servico
from core.dashboard import dashboard_context


class LocalVisitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('gestor-local-visitas')
        cls.staff = get_user_model().objects.create_user('equipe-visitas', is_staff=True)
        cls.other = get_user_model().objects.create_user('outro-local-visitas', is_staff=True)

    def setUp(self):
        self.client.force_login(self.admin)
        self.data = {'categoria': 'visita', 'quantidade_pessoas': 5, 'data': date(2099, 11, 10),
                     'hora_inicio': time(9), 'hora_termino': time(10), 'observacoes': 'Trazer material'}

    def create(self, actor=None, **changes):
        return save_booking(actor=actor or self.admin, data={**self.data, **changes})

    def payload(self, **changes):
        return {'quantidade_pessoas': '5', 'data': '2099-11-10', 'hora_inicio': '09:00',
                'hora_termino': '10:00', 'observacoes': 'Trazer material', **changes}

    def test_visit_business_fields_are_only_the_requested_five_and_form_uses_them(self):
        fields = {field.name for field in AgendaVisita._meta.concrete_fields}
        self.assertTrue({'quantidade_pessoas', 'data', 'hora_inicio', 'hora_termino', 'observacoes'} <= fields)
        self.assertFalse({'titulo', 'sala', 'motivo', 'inicio', 'fim'} & fields)
        self.assertEqual([field.name for field in VisitForm().visible_fields()],
                         ['quantidade_pessoas', 'data', 'hora_inicio', 'hora_termino', 'observacoes'])
        self.assertRedirects(self.client.get('/agenda/novo/?categoria=visita'), '/agenda/visitas/novo/')
        response = self.client.get('/agenda/visitas/novo/')
        for field in ('titulo', 'sala', 'motivo', 'objeto'):
            self.assertNotContains(response, f'name="{field}"')

    def test_admin_confirmation_creates_local_visit_and_full_detail_history(self):
        response = self.client.post('/agenda/visitas/novo/', self.payload())
        booking = AgendaVisita.objects.get()
        self.assertRedirects(response, f'/agenda/visita/{booking.pk}/')
        self.assertEqual((booking.situacao, booking.quantidade_pessoas, booking.criado_por), ('confirmado', 5, self.admin))
        self.assertEqual(booking.eventos.get().alteracoes['data']['novo'], '2099-11-10')
        detail = self.client.get(response.url)
        self.assertContains(detail, 'Trazer material')
        self.assertContains(detail, 'Quantidade de pessoas')
        self.assertNotContains(detail, 'Título')
        self.assertNotContains(detail, 'Sala')
        self.assertContains(self.client.get(f'/agenda/visita/{booking.pk}/historico/'), 'Criar')

    def test_staff_request_is_pending_then_admin_approves_locally(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post('/agenda/visitas/novo/', self.payload()).status_code, 302)
        booking = AgendaVisita.objects.get()
        self.assertEqual(booking.situacao, 'pendente')
        self.assertEqual(dashboard_context(self.staff, now=booking.inicio)['bookings'], [])
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/')
        self.assertContains(response, f'/agenda/visita/{booking.pk}/avaliar/')
        self.assertNotContains(response, 'AgroHub')
        self.assertRedirects(self.client.post(f'/agenda/visita/{booking.pk}/avaliar/',
            {'versao': 1, 'decisao': 'aprovar'}), '/agenda/solicitacoes/')
        booking.refresh_from_db()
        self.assertEqual((booking.situacao, booking.versao, booking.avaliado_por), ('confirmado', 2, self.admin))
        self.assertEqual([row.pk for row in dashboard_context(self.staff, now=booking.inicio)['bookings']], [booking.pk])
        confirmed = self.client.get('/agenda/solicitacoes/', {'status': 'confirmada'})
        self.assertEqual([row.pk for row in confirmed.context['object_list']], [booking.pk])

    def test_invalid_quantity_period_and_removed_fields_never_save(self):
        for change in ({'quantidade_pessoas': '0'}, {'quantidade_pessoas': '-1'},
                       {'hora_termino': '08:00'}, {'data': 'inválida'}, {'sala': 'inovalab'},
                       {'titulo': 'Visita remota'}, {'motivo': 'Não permitido'}, {'objeto': '1'},
                       {'versao': '1'}, {'situacao': 'confirmado'}):
            with self.subTest(change=change):
                response = self.client.post('/agenda/visitas/novo/', self.payload(**change))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
        self.assertFalse(AgendaVisita.objects.exists())
        self.assertFalse(EventoAgendamento.objects.exists())

    def test_conflicting_confirmed_visits_and_approval_are_blocked_and_adjacent_is_allowed(self):
        self.create()
        with self.assertRaises(BookingConflict):
            self.create(hora_inicio=time(9, 30), hora_termino=time(10, 30))
        pending = self.create(actor=self.staff)
        with self.assertRaises(BookingConflict):
            review_booking(actor=self.admin, category='visita', booking_id=pending.pk, expected_version=1, decision='aprovar')
        pending.refresh_from_db()
        self.assertEqual((pending.situacao, pending.eventos.count()), ('pendente', 1))
        self.assertEqual(self.create(hora_inicio=time(10), hora_termino=time(11)).situacao, 'confirmado')

    def test_edit_cancel_versions_history_and_slot_release(self):
        booking = self.create()
        response = self.client.post(f'/agenda/visita/{booking.pk}/editar/', self.payload(versao='1', quantidade_pessoas='8'))
        self.assertRedirects(response, booking.get_absolute_url())
        booking.refresh_from_db()
        self.assertEqual((booking.quantidade_pessoas, booking.versao), (8, 2))
        self.assertEqual(self.client.post(f'/agenda/visita/{booking.pk}/editar/', self.payload(versao='1')).status_code, 409)
        cancel_booking(actor=self.admin, category='visita', booking_id=booking.pk, expected_version=2)
        booking.refresh_from_db()
        self.assertEqual((booking.versao, booking.eventos.count()), (3, 3))
        self.assertEqual(self.create().situacao, 'confirmado')
        personal = self.client.get('/agenda/meus/', {'situacao': 'cancelado'})
        self.assertEqual([row.pk for row in personal.context['object_list']], [booking.pk])
        self.assertContains(self.client.get(f'/agenda/meus/visitas/{booking.pk}/'), 'Cancelado')

    def test_rejection_and_cancelled_requests_are_filterable_locally(self):
        rejected = self.create(actor=self.staff)
        review_booking(actor=self.admin, category='visita', booking_id=rejected.pk, expected_version=1, decision='rejeitar')
        cancelled = self.create(actor=self.staff)
        cancel_booking(actor=self.admin, category='visita', booking_id=cancelled.pk, expected_version=1)
        for status, booking in (('recusada', rejected), ('cancelada', cancelled)):
            response = self.client.get('/agenda/solicitacoes/', {'status': status})
            self.assertEqual([row.pk for row in response.context['object_list']], [booking.pk])
            self.assertNotContains(response, 'value="aprovar"')

    def test_other_owner_cannot_read_or_act_and_staff_cannot_edit_or_cancel(self):
        booking = self.create(actor=self.staff)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(booking.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(f'/agenda/meus/visitas/{booking.pk}/').status_code, 404)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(f'/agenda/meus/visitas/{booking.pk}/'), 'Trazer material')
        for suffix in ('editar/', 'cancelar/', 'avaliar/'):
            self.assertEqual(self.client.post(f'/agenda/visita/{booking.pk}/{suffix}', self.payload()).status_code, 403)

    def test_database_rejects_nonpositive_people_and_period_and_event_with_two_agendas(self):
        base = {key: value for key, value in self.data.items() if key != 'categoria'}
        for changes in ({'quantidade_pessoas': 0}, {'hora_termino': time(9)}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                AgendaVisita.objects.create(**{**base, **changes})
        visit = self.create()
        service = AgendaServico.objects.create(servico=Servico.objects.first(), motivo='Serviço', inicio=visit.inicio, fim=visit.fim)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventoAgendamento.objects.create(agenda_servico=service, agenda_visita=visit, ator_nome='Inválido', acao='criar')

    def test_api_uses_only_visit_fields_for_create_edit_list_history_and_cancel(self):
        client = APIClient()
        client.force_login(self.admin)
        data = {**self.payload(), 'categoria': 'visita', 'quantidade_pessoas': 5}
        response = client.post('/api/v1/agendamentos/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse({'sala', 'titulo', 'motivo', 'objeto', 'inicio', 'fim'} & set(response.data))
        pk = response.data['id']
        url = f'/api/v1/agendamentos/visita/{pk}/'
        self.assertEqual(client.get(url).data['quantidade_pessoas'], 5)
        for field in ('sala', 'titulo', 'motivo', 'objeto', 'inicio', 'fim'):
            self.assertEqual(client.patch(url, {'versao': 1, field: 'Inválido'}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'versao': 1, 'quantidade_pessoas': 8}, format='json').status_code, 200)
        self.assertEqual(client.get('/api/v1/agendamentos/', {'categoria': 'visita'}).data['count'], 1)
        self.assertEqual(client.get(url + 'historico/').data['count'], 2)
        self.assertEqual(client.delete(url, {'versao': 2}, format='json').status_code, 204)

    def test_csrf_and_data_validation_are_required_before_creation(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        self.assertEqual(secure.post('/agenda/visitas/novo/', self.payload()).status_code, 403)
        secure.get('/agenda/visitas/novo/')
        token = secure.cookies['csrftoken'].value
        self.assertEqual(secure.post('/agenda/visitas/novo/', self.payload(), HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertEqual(AgendaVisita.objects.count(), 1)

    def test_calendar_local_counts_without_provider_and_preserves_equal_ids(self):
        visit = self.create()
        service = AgendaServico.objects.create(pk=visit.pk, servico=Servico.objects.first(), motivo='Serviço diferente',
                                               criado_por=self.admin, inicio=visit.inicio, fim=visit.fim)
        response = self.client.get('/agenda/', {'mes': '2099-11'})
        self.assertEqual(response.context['category_counts'], {'servico': 1, 'equipamento': 0, 'visita': 1})
        day = next(day for week in response.context['weeks'] for day in week if day['in_month'] and day['date'].day == 10)
        self.assertEqual(day['count'], 2)
        self.assertContains(self.client.get(service.get_absolute_url()), 'Serviço diferente')
        self.assertNotContains(self.client.get(visit.get_absolute_url()), 'Serviço diferente')

    def test_changing_service_category_cannot_edit_visit_with_same_id(self):
        visit = self.create()
        service = AgendaServico.objects.create(pk=visit.pk, servico=Servico.objects.first(), motivo='Serviço',
                                               criado_por=self.admin, inicio=visit.inicio, fim=visit.fim)
        response = self.client.post(f'/agenda/servico/{service.pk}/editar/',
                                    self.payload(categoria='visita', versao='1', quantidade_pessoas='25'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        visit.refresh_from_db()
        service.refresh_from_db()
        self.assertEqual((visit.quantidade_pessoas, visit.versao, visit.eventos.count()), (5, 1, 1))
        self.assertEqual((service.motivo, service.versao), ('Serviço', 1))


class VisitsAccountsBoundaryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stub = AccountsStub()
        cls.config = override_settings(AGROHUB_API_BASE_URL=cls.stub.url, DEBUG=True)
        cls.config.enable()

    @classmethod
    def tearDownClass(cls):
        cls.config.disable()
        cls.stub.close()
        super().tearDownClass()

    def setUp(self):
        self.stub.reset()
        self.stub.state['profile']['roles'] = ['admin']
        self.assertEqual(self.client.post('/entrar/', {'username': 'agro-ana', 'password': PASSWORD}).status_code, 302)

    def test_entire_visit_flow_and_dashboard_keep_accounts_events_but_never_call_visit_api(self):
        payload = {'quantidade_pessoas': 5, 'data': '2099-11-10', 'hora_inicio': '09:00',
                   'hora_termino': '10:00', 'observacoes': 'Visita local vinculada'}
        self.client.get('/agenda/visitas/novo/')
        self.assertEqual(self.client.post('/agenda/visitas/novo/', payload).status_code, 302)
        booking = AgendaVisita.objects.get()
        for path in ('/agenda/', '/agenda/meus/', '/agenda/solicitacoes/', booking.get_absolute_url(),
                     f'/agenda/meus/visitas/{booking.pk}/'):
            self.assertEqual(self.client.get(path).status_code, 200)
        with patch('core.views.load_events', return_value=([], False)) as events:
            self.assertEqual(self.client.get('/index/').status_code, 200)
            events.assert_called_once()
        self.assertEqual(self.client.post(f'/agenda/visita/{booking.pk}/editar/', {**payload, 'versao': 1}).status_code, 302)
        self.assertEqual(self.client.post(f'/agenda/visita/{booking.pk}/cancelar/', {'versao': 2}).status_code, 302)
        self.assertFalse(any('/agendamentos/' in row[1] for row in self.stub.state['requests']))
        self.assertTrue(any('/accounts/me/' in row[1] for row in self.stub.state['requests']))

    def test_regular_account_and_provider_staff_can_read_all_own_local_visits(self):
        self.client.post('/agenda/visitas/novo/', {'quantidade_pessoas': 5, 'data': '2099-11-10',
            'hora_inicio': '09:00', 'hora_termino': '10:00', 'observacoes': 'Minha visita'})
        booking = AgendaVisita.objects.get()
        other = get_user_model().objects.create_user('dono-alheio')
        AgendaVisita.objects.create(criado_por=other, quantidade_pessoas=2, data=date(2099, 11, 11),
                                   hora_inicio=time(9), hora_termino=time(10), observacoes='SEGREDO')
        self.stub.state['profile']['roles'] = ['student']
        response = self.client.get('/agenda/meus/')
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertNotContains(response, 'SEGREDO')
        self.assertContains(self.client.get(f'/agenda/meus/visitas/{booking.pk}/'), 'Minha visita')
        self.assertEqual(self.client.get('/agenda/novo/').status_code, 403)
        self.assertFalse(any('/agendamentos/' in row[1] for row in self.stub.state['requests']))
