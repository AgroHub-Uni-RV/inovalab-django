from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from accounts.agrohub.client import AgroHubError
from accounts.tests.agrohub_stub import PASSWORD
from agenda.models import AgendaServico, AgendaEquipamento, EventoAgendamento
from agenda.tests.agrohub_stub import ReservationsStub


def visit_fixture(pk=101, **changes):
    return {'id': pk, 'sala': {'id': 1, 'slug': 'laboratorio-inovalab', 'nome': 'Laboratório InovaLab'},
            'titulo': 'Visita remota', 'nome_solicitante': 'Ana Silva', 'quantidade_pessoas': 5,
            'status': 'pendente', 'inicio': '2099-11-10T09:00:00-03:00',
            'fim': '2099-11-10T10:00:00-03:00', 'data': '2099-11-10', 'hora_inicio': '09:00',
            'hora_fim': '10:00', 'observacoes': 'Observação remota',
            'created_at': '2026-10-07T12:00:00Z', 'updated_at': '2026-10-07T12:00:00Z', **changes}


class VisitsProviderMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stub = ReservationsStub()
        cls.provider_settings = override_settings(AGROHUB_API_BASE_URL=cls.stub.url, DEBUG=True)
        cls.provider_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.provider_settings.disable()
        cls.stub.close()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.stub.reset()
        self.login()

    def login(self, roles=None):
        self.stub.state['profile']['roles'] = ['staff'] if roles is None else roles
        self.assertEqual(self.client.post('/entrar/', {'username': 'agro-ana', 'password': PASSWORD}).status_code, 302)

    def writes(self):
        return [row for row in self.stub.state['requests'] if '/agendamentos/' in row[1] and row[0] != 'GET']

    def assert_no_local_visits(self):
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))

    def payload(self, **changes):
        return {'sala': 'laboratorio-inovalab', 'titulo': 'Visita nova', 'quantidade_pessoas': 7,
                'data': '2099-11-10', 'hora_inicio': '09:00', 'hora_fim': '10:00',
                'observacoes': 'Trazer material', **changes}


class RemoteVisitAdapterTests(VisitsProviderMixin, TestCase):
    def request(self):
        request = RequestFactory().get('/')
        request.user = get_user_model().objects.get(agrohub_id=42)
        request.session = self.client.session
        return request

    def test_create_uses_provider_status_and_preserves_all_fields(self):
        from agenda.remote_requests import save_reservation
        self.login(['admin'])
        remote = save_reservation(self.request(), self.payload())
        self.assertEqual((remote.status, remote.titulo, remote.quantidade_pessoas, remote.observacoes),
                         ('pendente', 'Visita nova', 7, 'Trazer material'))
        self.assertNotIn('status', self.writes()[0][2])
        self.assert_no_local_visits()

    def test_get_detail_is_not_a_collection_and_edit_omits_forbidden_fields(self):
        from agenda.remote_requests import get_reservation, save_reservation
        self.stub.state['reservas'] = [visit_fixture()]
        remote = get_reservation(self.request(), 101)
        self.assertEqual(remote.observacoes, 'Observação remota')
        payload = self.payload(titulo='Visita editada')
        payload.pop('sala')
        result = save_reservation(self.request(), payload, reservation_id=101)
        self.assertEqual(result.titulo, 'Visita editada')
        self.assertNotIn('sala', self.writes()[0][2])
        self.assertNotIn('status', self.writes()[0][2])
        self.assertFalse(any('/reservas/?' in row[1] for row in self.stub.state['requests']))
        self.assert_no_local_visits()

    def test_cancel_confirmed_future_uses_cancel_action(self):
        from agenda.remote_requests import cancel_reservation
        self.stub.state['reservas'] = [visit_fixture(status='confirmada')]
        result = cancel_reservation(self.request(), 101)
        self.assertEqual(result.status, 'cancelada')
        self.assertEqual(self.writes()[0][:3], ('POST', '/api/v1/agendamentos/reservas/101/cancelar/', {}))
        self.assert_no_local_visits()

    def test_rejects_unknown_fields_bad_period_quantity_and_foreign_room_before_write(self):
        from agenda.remote_requests import save_reservation
        for changes in ({'status': 'confirmada'}, {'solicitante': 42}, {'quantidade_pessoas': True},
                        {'quantidade_pessoas': 0}, {'hora_inicio': '10:00:00'}, {'hora_fim': '08:00'},
                        {'data': 'not-a-date'}, {'sala': 'outra-sala'}):
            with self.subTest(changes=changes), self.assertRaises(AgroHubError):
                save_reservation(self.request(), self.payload(**changes))
        self.assertFalse(self.writes())

    def test_foreign_detail_and_unlinked_account_fail_before_mutation(self):
        from agenda.remote_requests import get_reservation, save_reservation
        self.stub.state['reservas'] = [visit_fixture(sala={'id': 2, 'slug': 'outro', 'nome': 'Outro'})]
        with self.assertRaises(AgroHubError) as error:
            get_reservation(self.request(), 101)
        self.assertEqual(error.exception.status, 403)
        request = self.request()
        request.user.agrohub_id = None
        with self.assertRaises(AgroHubError):
            save_reservation(request, self.payload())
        self.assertFalse(self.writes())

    def test_cancel_rejects_terminal_and_past_reservations(self):
        from agenda.remote_requests import cancel_reservation
        for status in ('cancelada', 'recusada'):
            self.stub.state['reservas'] = [visit_fixture(status=status)]
            with self.assertRaises(AgroHubError):
                cancel_reservation(self.request(), 101)
        self.stub.state['reservas'] = [visit_fixture(inicio='2020-11-10T09:00:00-03:00', fim='2020-11-10T10:00:00-03:00')]
        with self.assertRaises(AgroHubError):
            cancel_reservation(self.request(), 101)
        self.assertFalse(self.writes())

    def test_uncertain_create_is_never_retried_or_claimed_success(self):
        from agenda.remote_requests import save_reservation
        self.stub.state['create_uncertain'] = True
        with self.assertRaises(AgroHubError):
            save_reservation(self.request(), self.payload())
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(len(self.stub.state['reservas']), 1)
        self.assert_no_local_visits()

    def test_malformed_detail_and_write_responses_fail_safely(self):
        from agenda.remote_requests import get_reservation, save_reservation
        for changes in ({'status': []}, {'observacoes': None}, {'created_at': 'invalid'},
                        {'quantidade_pessoas': True}, {'fim': '2099-11-10T08:00:00-03:00'}):
            self.stub.state['reservas'] = [visit_fixture(**changes)]
            with self.subTest(changes=changes), self.assertRaises(AgroHubError):
                get_reservation(self.request(), 101)
        self.stub.state['omit_id'] = True
        with self.assertRaises(AgroHubError):
            save_reservation(self.request(), self.payload())
        self.assert_no_local_visits()

    def test_create_response_cannot_change_submitted_time_seconds(self):
        from agenda.remote_requests import save_reservation
        reply = visit_fixture(titulo='Visita nova', quantidade_pessoas=7, observacoes='Trazer material',
                              inicio='2099-11-10T09:00:30-03:00')
        self.stub.state['responses'][('POST', '/api/v1/agendamentos/reservas/')] = (201, reply)
        with self.assertRaises(AgroHubError):
            save_reservation(self.request(), self.payload())
        self.assert_no_local_visits()

    def test_status_only_action_cannot_change_original_reservation_fields(self):
        from agenda.remote_requests import cancel_reservation, decide_reservation
        for function, route, verb, result_status in ((cancel_reservation, 'cancelar/', 'POST', 'cancelada'),
                                                     (decide_reservation, '', 'PATCH', 'confirmada')):
            self.stub.state['reservas'] = [visit_fixture()]
            self.stub.state['responses'] = {(verb, '/api/v1/agendamentos/reservas/101/'+route):
                                           (200, visit_fixture(status=result_status, quantidade_pessoas=9))}
            with self.subTest(action=function.__name__), self.assertRaises(AgroHubError):
                function(self.request(), 101, 'confirmar') if function == decide_reservation else function(self.request(), 101)
        self.assert_no_local_visits()

    @override_settings(AGROHUB_API_TIMEOUT=0.05)
    def test_timeout_after_create_does_not_retry_an_uncertain_write(self):
        from agenda.remote_requests import save_reservation
        self.stub.state['create_delay'] = 0.15
        with self.assertRaises(AgroHubError):
            save_reservation(self.request(), self.payload())
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(len(self.stub.state['reservas']), 1)
        self.assert_no_local_visits()
