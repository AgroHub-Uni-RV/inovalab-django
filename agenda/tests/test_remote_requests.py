from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.tests.agrohub_stub import PASSWORD
from agenda.models import Agendamento, EventoAgendamento, ReservaAgroHub
from agenda.tests.agrohub_stub import ReservationsStub
from catalogo.models import Servico


class PendingRequestsStub(ReservationsStub):
    def reset(self):
        super().reset()
        self.state.update(rooms=[dict(self.state['sala'])], listing_error=None,
                          listing_page_size=100, ignore_filters=False, remote_next=None, malformed=None)

    def dispatch_extra(self, handler, data):
        if self.state['expired'] or handler.headers.get('Authorization') not in ('Bearer access-1', 'Bearer access-2'):
            return super().dispatch_extra(handler, data)
        path = urlsplit(handler.path).path
        if handler.command != 'GET' or path not in ('/api/v1/agendamentos/salas/', '/api/v1/agendamentos/reservas/'):
            return super().dispatch_extra(handler, data)
        if self.state['listing_error']:
            handler.reply(self.state['listing_error'], {})
            return True
        if self.state['malformed'] is not None:
            handler.reply(200, self.state['malformed'])
            return True
        params = parse_qs(urlsplit(handler.path).query)
        rows = self.state['rooms'] if path.endswith('salas/') else self.state['reservas']
        if path.endswith('reservas/') and not self.state['ignore_filters']:
            rows = [row for row in rows if row['sala']['slug'] == params['sala'][0] and row['status'] == params['status'][0]]
        page, size = int(params.get('page', ['1'])[0]), self.state['listing_page_size']
        next_page = None
        if len(rows) > page*size:
            next_page = self.state['remote_next'] or f'{self.origin}{path}?page={page+1}'
        handler.reply(200, {'results': rows[(page-1)*size:page*size], 'count': len(rows), 'next': next_page})
        return True


class RemotePendingRequestsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stub = PendingRequestsStub()
        cls.provider_settings = override_settings(AGROHUB_API_BASE_URL=cls.stub.url, DEBUG=True)
        cls.provider_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.provider_settings.disable()
        cls.stub.close()
        super().tearDownClass()

    def setUp(self):
        self.stub.reset()
        self.login()

    def login(self, roles=None):
        self.stub.state['profile']['roles'] = ['admin'] if roles is None else roles
        response = self.client.post('/entrar/', {'username': 'agro-ana', 'password': PASSWORD})
        self.assertEqual(response.status_code, 302)

    def reservation(self, pk=101, *, room=None, **overrides):
        return {'id': pk, 'sala': room or dict(self.stub.state['sala']), 'titulo': 'Pedido do monólito',
                'nome_solicitante': 'Pessoa externa', 'quantidade_pessoas': 5, 'status': 'pendente',
                'inicio': '2026-11-10T09:00:00-03:00', 'fim': '2026-11-10T10:00:00-03:00',
                'created_at': '2026-10-07T12:00:00Z', **overrides}

    def listing_requests(self):
        return [row for row in self.stub.state['requests'] if '/agendamentos/' in row[1]]

    def test_remote_pending_reservations_display_without_local_copy_or_write_actions(self):
        self.stub.state['reservas'] = [self.reservation(), self.reservation(102, status='confirmada')]
        user = get_user_model().objects.get(agrohub_id=42)
        Agendamento.objects.create(servico=Servico.objects.first(), motivo='Pedido somente local',
            inicio='2026-11-10T12:00:00Z', fim='2026-11-10T13:00:00Z', criado_por=user, situacao='pendente')
        before = (Agendamento.objects.count(), EventoAgendamento.objects.count(), ReservaAgroHub.objects.count())
        response = self.client.get('/agenda/solicitacoes/')
        self.assertContains(response, '#101')
        self.assertContains(response, 'Pedido do monólito')
        self.assertContains(response, 'Pessoa externa')
        self.assertContains(response, '10/11/2026 09:00')
        self.assertEqual(response.context['paginator'].count, 1)
        for value in ('#102', 'Pedido somente local', '/avaliar/', 'name="decisao"', 'name="categoria"', 'name="situacao"'):
            self.assertNotContains(response, value)
        self.assertEqual(before, (Agendamento.objects.count(), EventoAgendamento.objects.count(), ReservaAgroHub.objects.count()))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(all(row[0] == 'GET' and row[3] == 'Bearer access-1' for row in self.listing_requests()))
        self.assertFalse(user.is_staff)

    def test_all_inovalab_rooms_including_inactive_and_only_pending_rows(self):
        second = {**self.stub.state['sala'], 'id': 2, 'slug': 'sala-antiga', 'nome': 'Sala antiga', 'ativa': False}
        foreign = {**self.stub.state['sala'], 'id': 3, 'slug': 'outra-sala', 'site_code': 'agrohub'}
        self.stub.state.update(rooms=[self.stub.state['sala'], second, foreign], ignore_filters=True,
            reservas=[self.reservation(), self.reservation(102, room=second), self.reservation(103, room=foreign),
                      self.reservation(104, status='confirmada'), self.reservation(105, status='cancelada'),
                      self.reservation(106, status='recusada')])
        response = self.client.get('/agenda/solicitacoes/', {'situacao': 'confirmada'})
        self.assertEqual({row.id for row in response.context['object_list']}, {101, 102})
        requests = self.listing_requests()
        self.assertIn('ativas=false', requests[0][1])
        self.assertTrue(all('status=pendente' in row[1] for row in requests if '/reservas/' in row[1]))
        self.assertFalse(any('sala=outra-sala' in row[1] for row in requests))

    def test_remote_pagination_uses_own_origin_and_display_paginates_25(self):
        self.stub.state.update(reservas=[self.reservation(pk) for pk in range(101, 127)],
                               listing_page_size=10, remote_next='https://untrusted.example/collect-token')
        response = self.client.get('/agenda/solicitacoes/')
        self.assertEqual(response.context['paginator'].count, 26)
        self.assertEqual(len(response.context['object_list']), 25)
        self.assertEqual(response.context['object_list'][0].id, 126)
        self.assertContains(response, '?page=2')
        second = self.client.get('/agenda/solicitacoes/', {'page': 2})
        self.assertEqual([row.id for row in second.context['object_list']], [101])
        self.assertTrue(all(row[1].startswith('/api/v1/agendamentos/') for row in self.listing_requests()))

    def test_search_month_and_creation_order_match_remote_listing(self):
        self.stub.state['reservas'] = [self.reservation(), self.reservation(102, titulo='Outro pedido',
            created_at='2026-10-06T12:00:00Z'), self.reservation(103, inicio='2026-12-10T09:00:00-03:00',
            fim='2026-12-10T10:00:00-03:00', created_at='2026-10-08T12:00:00Z')]
        response = self.client.get('/agenda/solicitacoes/')
        self.assertEqual([row.id for row in response.context['object_list']], [103, 101, 102])
        filtered = self.client.get('/agenda/solicitacoes/', {'q': 'pessoa EXTERNA', 'mes': '2026-11'})
        self.assertEqual([row.id for row in filtered.context['object_list']], [101, 102])
        self.assertEqual(self.client.get('/agenda/solicitacoes/', {'q': '102'}).context['paginator'].count, 1)
        self.assertEqual(self.client.get('/agenda/solicitacoes/', {'mes': '2026-99'}).status_code, 400)

    def test_failure_is_not_an_empty_result_and_refresh_keeps_identity(self):
        self.stub.state['listing_error'] = 503
        response = self.client.get('/agenda/solicitacoes/')
        self.assertContains(response, 'Não foi possível consultar', status_code=503)
        self.assertNotContains(response, 'Nenhuma reserva pendente', status_code=503)
        self.assertContains(self.client.get('/agenda/solicitacoes/', {'page': 2}),
                            'Não foi possível consultar', status_code=503)
        before_refresh = len(self.listing_requests())
        self.stub.state.update(listing_error=None, expired=True, reservas=[self.reservation()])
        self.assertContains(self.client.get('/agenda/solicitacoes/'), '#101')
        refreshed_requests = self.listing_requests()[before_refresh:]
        self.assertTrue(refreshed_requests)
        self.assertTrue(all(row[3] == 'Bearer access-2' for row in refreshed_requests))

    def test_permission_denial_and_local_admin_without_agrohub_session(self):
        self.stub.state['listing_error'] = 403
        self.assertContains(self.client.get('/agenda/solicitacoes/'), 'conta autorizada', status_code=403)
        self.login(['staff'])
        before = len(self.listing_requests())
        self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 403)
        self.assertEqual(len(self.listing_requests()), before)
        local = get_user_model().objects.create_superuser('admin-local')
        self.client.force_login(local)
        self.assertContains(self.client.get('/agenda/solicitacoes/'), 'conta administrativa vinculada ao AgroHub')
        self.assertEqual(len(self.listing_requests()), before)

    def test_invalid_payload_is_rejected_and_external_text_is_escaped(self):
        for payload in ({'results': {}}, {'results': [None]}, {'results': [], 'next': True}):
            self.stub.state['malformed'] = payload
            self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 503)
        self.stub.state['malformed'] = None
        self.stub.state['ignore_filters'] = True
        for changes in ({'id': True}, {'inicio': '2026-11-10T09:00:00'}, {'fim': 'invalid'},
                        {'quantidade_pessoas': 0}, {'created_at': 'invalid'},
                        {'inicio': '0001-01-01T00:00:00Z'}, {'sala': {}}, {'status': 'invalid'}):
            self.stub.state['reservas'] = [self.reservation(**changes)]
            self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 503)
        self.stub.state['reservas'] = [self.reservation(titulo='<script>alert(1)</script>')]
        response = self.client.get('/agenda/solicitacoes/')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_unbounded_remote_pagination_fails_without_partial_results(self):
        self.stub.state['malformed'] = {'results': [], 'next': 'https://untrusted.example/next'}
        response = self.client.get('/agenda/solicitacoes/')
        self.assertContains(response, 'Não foi possível consultar', status_code=503)
        self.assertEqual(len(self.listing_requests()), 40)
        self.assertNotContains(response, 'Nenhuma reserva pendente', status_code=503)

    def test_get_and_head_are_read_only_and_empty_result_is_explicit(self):
        response = self.client.get('/agenda/solicitacoes/')
        self.assertContains(response, 'Nenhuma reserva pendente no AgroHub')
        self.assertEqual(self.client.head('/agenda/solicitacoes/').status_code, 200)
        self.assertEqual(self.client.post('/agenda/solicitacoes/', {}).status_code, 405)
        self.assertFalse(Agendamento.objects.exists())
