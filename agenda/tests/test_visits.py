from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from agenda.models import AgendaServico, AgendaEquipamento, EventoAgendamento
from agenda.services import save_booking
from agenda.tests.test_agrohub import VisitsProviderMixin, visit_fixture


class RemoteOnlyVisitBoundaryTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('gestor-visitas')
        self.client = APIClient()
        self.client.force_login(self.admin)

    def test_local_api_and_services_reject_visits_without_any_persistence(self):
        data = {'categoria': 'visita', 'inicio': '2026-11-01T14:00:00-03:00', 'fim': '2026-11-01T15:00:00-03:00'}
        response = self.client.post('/api/v1/agendamentos/', data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('categoria', response.data)
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, data=data)
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))

    def test_visit_creation_navigation_uses_remote_route(self):
        response = self.client.get('/agenda/novo/?categoria=visita')
        self.assertRedirects(response, '/agenda/visitas/novo/', fetch_redirect_response=False)
        self.assertContains(self.client.get('/agenda/novo/'), '/agenda/visitas/novo/')


class RemoteVisitFlowTests(VisitsProviderMixin, TestCase):
    def test_create_pending_visit_redirects_to_detail_and_remains_discoverable(self):
        self.stub.state['profile']['is_staff'] = False
        response = self.client.post('/agenda/visitas/novo/', self.payload())
        self.assertRedirects(response, '/agenda/visitas/101/', fetch_redirect_response=False)
        detail = self.client.get('/agenda/visitas/101/')
        self.assertContains(detail, 'Trazer material')
        self.assertContains(detail, 'Pendente')
        self.assertContains(self.client.get('/agenda/'), '/agenda/meus/')
        self.assertContains(self.client.get('/agenda/visitas/'), 'Visita nova')
        self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 403)
        self.assert_no_local_visits()

    def test_edit_preserves_room_quantity_title_observations_and_sends_no_room_or_status(self):
        self.stub.state['reservas'] = [visit_fixture()]
        response = self.client.get('/agenda/visitas/101/editar/')
        for text in ('Visita remota', 'Laboratório InovaLab', 'Observação remota', 'value="5"'):
            self.assertContains(response, text)
        payload = self.payload(titulo='Visita alterada')
        payload.pop('sala')
        self.assertEqual(self.client.post('/agenda/visitas/101/editar/', payload).status_code, 302)
        self.assertNotIn('sala', self.writes()[0][2])
        self.assertNotIn('status', self.writes()[0][2])
        self.assertContains(self.client.get('/agenda/visitas/101/'), 'Visita alterada')
        self.assert_no_local_visits()

    def test_confirmed_future_can_cancel_but_staff_cannot_edit_it(self):
        self.stub.state['reservas'] = [visit_fixture(status='confirmada')]
        detail = self.client.get('/agenda/visitas/101/')
        self.assertContains(detail, '/agenda/visitas/101/cancelar/')
        self.assertNotContains(detail, '/agenda/visitas/101/editar/')
        self.assertEqual(self.client.post('/agenda/visitas/101/editar/', self.payload()).status_code, 403)
        self.assertEqual(self.client.get('/agenda/visitas/101/cancelar/').status_code, 200)
        self.assertFalse(self.writes())
        self.assertEqual(self.client.post('/agenda/visitas/101/cancelar/', {}).status_code, 302)
        self.assert_no_local_visits()

    def test_invalid_form_forged_fields_and_cancel_payload_never_write(self):
        for changes in ({'hora_fim': '08:00'}, {'status': 'confirmada'}, {'quantidade_pessoas': '0'},
                        {'solicitante': '42'}, {'titulo': ['primeiro', 'segundo']}):
            self.assertEqual(self.client.post('/agenda/visitas/novo/', self.payload(**changes)).status_code, 400)
        self.stub.state['reservas'] = [visit_fixture()]
        self.assertEqual(self.client.post('/agenda/visitas/101/cancelar/', {'versao': 1}).status_code, 400)
        self.assertFalse(self.writes())

    def test_csrf_and_provider_denial_prevent_local_success(self):
        from django.test import Client
        secure = Client(enforce_csrf_checks=True)
        secure.cookies = self.client.cookies
        self.assertEqual(secure.post('/agenda/visitas/novo/', self.payload()).status_code, 403)
        self.assertFalse(self.writes())
        self.stub.state['create_error'] = 403
        self.assertEqual(self.client.post('/agenda/visitas/novo/', self.payload()).status_code, 403)
        self.assert_no_local_visits()

    def test_uncertain_create_links_to_live_visits_without_retry(self):
        self.stub.state['create_uncertain'] = True
        response = self.client.post('/agenda/visitas/novo/', self.payload())
        self.assertContains(response, 'consulte suas visitas', status_code=503)
        self.assertContains(response, '/agenda/meus/', status_code=503)
        self.assertEqual(len(self.writes()), 1)
        self.assert_no_local_visits()

    def test_remote_unavailability_does_not_show_successful_zero_counter(self):
        self.stub.state['responses'][('GET', '/api/v1/agendamentos/reservas/?sala=laboratorio-inovalab&page=1&page_size=100')] = (503, {})
        response = self.client.get('/agenda/')
        self.assertEqual(response.context['category_counts']['visita'], None)
        self.assertContains(response, 'Visitas indisponíveis')

    def test_provider_ownership_and_mutation_denials_are_authoritative(self):
        self.stub.state['profile']['is_staff'] = False
        self.stub.state['reservas'] = [visit_fixture(owner_id=99)]
        for suffix in ('', 'editar/', 'cancelar/'):
            self.assertEqual(self.client.get('/agenda/visitas/101/'+suffix).status_code, 404)
        self.assertNotContains(self.client.get('/agenda/visitas/'), 'Visita remota')
        self.stub.state['reservas'] = [visit_fixture(owner_id=42)]
        for status in (400, 403, 404, 503):
            self.stub.state['responses'][('PATCH', '/api/v1/agendamentos/reservas/101/')] = (status, {})
            payload = self.payload()
            payload.pop('sala')
            self.assertEqual(self.client.post('/agenda/visitas/101/editar/', payload).status_code, status)
        self.assert_no_local_visits()

    def test_pending_staff_edit_succeeds_against_nonstaff_provider_policy(self):
        self.stub.state['profile']['is_staff'] = False
        self.stub.state['reservas'] = [visit_fixture(owner_id=42)]
        payload = self.payload(titulo='Mudança permitida')
        payload.pop('sala')
        self.assertEqual(self.client.post('/agenda/visitas/101/editar/', payload).status_code, 302)
        self.assertEqual(self.stub.state['reservas'][0]['titulo'], 'Mudança permitida')
        self.assert_no_local_visits()

    def test_foreign_room_details_and_creation_never_write(self):
        self.stub.state['reservas'] = [visit_fixture(sala={'id': 2, 'slug': 'estrangeira', 'nome': 'Outra sala'})]
        for suffix in ('', 'editar/', 'cancelar/'):
            self.assertEqual(self.client.get('/agenda/visitas/101/'+suffix).status_code, 403)
        self.assertEqual(self.client.post('/agenda/visitas/novo/', self.payload(sala='estrangeira')).status_code, 400)
        self.assertFalse(self.writes())

    def test_visits_filters_and_pagination_keep_remote_status_and_no_writes(self):
        self.stub.state['profile']['is_staff'] = False
        self.stub.state['reservas'] = [visit_fixture(pk, titulo='Pedido filtrado') for pk in range(101, 128)]
        self.stub.state['reservas'] += [visit_fixture(130, status='cancelada'),
                                       visit_fixture(131, titulo='Excluir por texto')]
        params = {'status': 'pendente', 'mes': '2099-11', 'q': 'filtrado'}
        response = self.client.get('/agenda/visitas/', params)
        self.assertEqual(response.context['paginator'].count, 27)
        self.assertEqual(len(response.context['object_list']), 25)
        self.assertContains(response, 'page=2')
        self.assertContains(response, 'status=pendente')
        second = self.client.get('/agenda/visitas/', {**params, 'page': 2})
        self.assertEqual([row.id for row in second.context['object_list']], [102, 101])
        self.assertEqual(self.client.get('/agenda/visitas/', {'mes': '2099-99'}).status_code, 400)
        self.assertFalse(self.writes())

    def test_csrf_valid_create_and_invalid_edit_cancel_are_explicit(self):
        from django.test import Client
        secure = Client(enforce_csrf_checks=True)
        secure.cookies = self.client.cookies
        secure.get('/agenda/visitas/novo/')
        token = secure.cookies['csrftoken'].value
        self.assertEqual(secure.post('/agenda/visitas/novo/', self.payload(), HTTP_X_CSRFTOKEN=token).status_code, 302)
        before = len(self.writes())
        for suffix in ('editar/', 'cancelar/'):
            self.assertEqual(secure.post('/agenda/visitas/101/'+suffix, {}).status_code, 403)
        self.assertEqual(len(self.writes()), before)
        self.assertEqual(secure.post('/agenda/visitas/101/cancelar/', {}, HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assert_no_local_visits()
