from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from accounts.tests.agrohub_stub import PASSWORD
from agenda.models import AgendaServico, AgendaEquipamento, EventoAgendamento
from agenda.tests.agrohub_stub import ReservationsStub
from catalogo.models import Servico


class PendingRequestsStub(ReservationsStub):
    def reset(self):
        super().reset()
        self.state.update(rooms=[dict(self.state['sala'])], listing_error=None,
                          listing_page_size=100, ignore_filters=False, remote_next=None, malformed=None,
                          action_error=None, action_uncertain=False, action_reply=None, detail_reply=None)

    def dispatch_extra(self, handler, data):
        if self.state['expired'] or handler.headers.get('Authorization') not in ('Bearer access-1', 'Bearer access-2'):
            return super().dispatch_extra(handler, data)
        path = urlsplit(handler.path).path
        if path.startswith('/api/v1/agendamentos/reservas/') and path != '/api/v1/agendamentos/reservas/':
            if handler.command == 'GET' and self.state['detail_reply'] is not None:
                handler.reply(200, self.state['detail_reply'])
                return True
            if handler.command in ('PATCH', 'POST'):
                remote_id = int(path.split('/')[5])
                remote = next((row for row in self.state['reservas'] if row['id'] == remote_id), None)
                if self.state['action_error']:
                    handler.reply(self.state['action_error'], {})
                elif remote is None:
                    handler.reply(404, {})
                else:
                    remote['status'] = 'cancelada' if path.endswith('/cancelar/') else data['status']
                    handler.reply(503 if self.state['action_uncertain'] else 200,
                                  self.state['action_reply'] if self.state['action_reply'] is not None else remote)
                return True
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
            rows = [row for row in rows if row['sala']['slug'] == params['sala'][0]
                    and ('status' not in params or row['status'] == params['status'][0])]
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

    def test_pending_and_confirmed_rows_stay_remote_without_local_writes(self):
        self.stub.state['reservas'] = [self.reservation(), self.reservation(102, status='confirmada')]
        user = get_user_model().objects.get(agrohub_id=42)
        AgendaServico.objects.create(servico=Servico.objects.first(), motivo='Pedido somente local',
            inicio='2026-11-10T12:00:00Z', fim='2026-11-10T13:00:00Z', criado_por=user, situacao='pendente')
        before = (AgendaServico.objects.count(), EventoAgendamento.objects.count(), AgendaEquipamento.objects.count())
        response = self.client.get('/agenda/solicitacoes/', {'status': 'pendente'})
        self.assertContains(response, '#101')
        self.assertContains(response, 'Pedido do monólito')
        self.assertContains(response, 'Pessoa externa')
        self.assertContains(response, '10/11/2026 09:00')
        self.assertEqual(response.context['paginator'].count, 1)
        for value in ('#102', 'Pedido somente local', '/avaliar/', 'name="categoria"', 'name="situacao"'):
            self.assertNotContains(response, value)
        self.assertContains(response, '/agenda/solicitacoes/101/decidir/')
        self.assertContains(response, 'value="confirmar"')
        self.assertContains(response, 'value="cancelar"')
        self.assertContains(response, 'value="recusar"')
        self.assertEqual(before,
                         (AgendaServico.objects.count(), EventoAgendamento.objects.count(), AgendaEquipamento.objects.count()))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(all(row[0] == 'GET' and row[3] == 'Bearer access-1' for row in self.listing_requests()))
        self.assertFalse(user.is_staff)

    def test_all_inovalab_rooms_including_inactive_exclude_foreign_rows(self):
        second = {**self.stub.state['sala'], 'id': 2, 'slug': 'sala-antiga', 'nome': 'Sala antiga', 'ativa': False}
        foreign = {**self.stub.state['sala'], 'id': 3, 'slug': 'outra-sala', 'site_code': 'agrohub'}
        self.stub.state.update(rooms=[self.stub.state['sala'], second, foreign], ignore_filters=True,
            reservas=[self.reservation(), self.reservation(102, room=second), self.reservation(103, room=foreign),
                      self.reservation(104, status='confirmada'), self.reservation(105, status='cancelada'),
                      self.reservation(106, status='recusada')])
        response = self.client.get('/agenda/solicitacoes/', {'situacao': 'confirmada'})
        self.assertEqual({row.id for row in response.context['object_list']}, {101, 102, 105, 106})
        pending = self.client.get('/agenda/solicitacoes/', {'status': 'pendente'})
        self.assertEqual({row.id for row in pending.context['object_list']}, {101, 102})
        requests = self.listing_requests()
        self.assertIn('ativas=false', requests[0][1])
        self.assertTrue(all('status=' not in row[1] for row in requests if '/reservas/' in row[1]))
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
                        {'inicio': '0001-01-01T00:00:00Z'}, {'sala': {}}, {'status': 'invalid'}, {'status': []}, {'status': {}}):
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
        self.assertContains(response, 'Nenhuma reserva no AgroHub')
        self.assertEqual(self.client.head('/agenda/solicitacoes/').status_code, 200)
        self.assertEqual(self.client.post('/agenda/solicitacoes/', {}).status_code, 405)
        self.assertFalse(AgendaServico.objects.exists())

    def writes(self):
        return [row for row in self.listing_requests() if row[0] != 'GET']

    def test_default_board_excludes_confirmed_and_only_pending_cards_have_actions(self):
        self.stub.state['reservas'] = [self.reservation(101), self.reservation(102, status='confirmada'),
                                       self.reservation(103, status='cancelada'), self.reservation(104, status='recusada')]
        response = self.client.get('/agenda/solicitacoes/')
        self.assertEqual(response.context['selected_status'], '')
        self.assertEqual(response.context['paginator'].count, 3)
        self.assertEqual(response.context['stat_counts'], {'all': 3, 'pendente': 1, 'cancelada': 1, 'recusada': 1})
        self.assertEqual({column['status']: [row.id for row in column['bookings']] for column in response.context['columns']},
                         {'pendente': [101], 'cancelada': [103], 'recusada': [104]})
        self.assertContains(response, 'class="module-tabs"')
        self.assertContains(response, 'class="task-board"')
        self.assertContains(response, 'class="kanban-card"', count=3)
        self.assertNotContains(response, 'aria-label="Confirmadas"')
        self.assertContains(response, 'value="confirmar"', count=1)
        self.assertContains(response, 'value="cancelar"', count=1)
        for pk in (102, 103, 104):
            self.assertNotContains(response, f'/agenda/solicitacoes/{pk}/decidir/')
        self.assertFalse(self.writes())

    def test_tabs_filter_remote_status_keep_shared_filters_and_totals(self):
        self.stub.state['reservas'] = [self.reservation(101), self.reservation(102, status='cancelada'),
            self.reservation(103, status='cancelada', titulo='Excluir por texto', nome_solicitante='Outra pessoa'),
            self.reservation(104, status='cancelada', inicio='2026-12-10T09:00:00-03:00', fim='2026-12-10T10:00:00-03:00')]
        params = {'q': 'Pessoa externa', 'mes': '2026-11', 'status': 'cancelada'}
        response = self.client.get('/agenda/solicitacoes/', params)
        self.assertEqual([row.id for row in response.context['object_list']], [102])
        self.assertEqual(response.context['stat_counts']['all'], 2)
        self.assertEqual(response.context['stat_counts']['pendente'], 1)
        self.assertEqual(response.context['stat_counts']['cancelada'], 1)
        self.assertContains(response, 'name="status" value="cancelada"')
        self.assertContains(response, 'class="task-board task-board-filtered"')
        self.assertContains(response, 'aria-label="Canceladas"><h2>Canceladas')
        self.assertNotContains(response, 'aria-label="Pendentes"><h2>Pendentes')
        self.assertNotContains(response, 'value="confirmar"')
        self.assertContains(response, 'q=Pessoa+externa&amp;mes=2026-11&amp;status=pendente')
        pending = self.client.get('/agenda/solicitacoes/', {**params, 'status': 'pendente'})
        self.assertEqual([row.id for row in pending.context['object_list']], [101])
        self.assertContains(pending, 'aria-label="Pendentes"><h2>Pendentes')
        invalid = self.client.get('/agenda/solicitacoes/', {'status': 'invalid'})
        self.assertEqual(invalid.context['selected_status'], '')
        self.assertEqual(invalid.context['paginator'].count, 4)
        empty = self.client.get('/agenda/solicitacoes/', {**params, 'q': 'Sem resultado'})
        self.assertContains(empty, 'Nenhuma reserva cancelada no AgroHub')

    def test_board_pagination_totals_and_tab_links_reset_page(self):
        self.stub.state.update(listing_page_size=10, reservas=[self.reservation(pk, status='cancelada') for pk in range(101, 133)]
                               + [self.reservation(201), self.reservation(202)])
        params = {'status': 'cancelada', 'q': 'Pedido', 'mes': '2026-11', 'page': 2}
        response = self.client.get('/agenda/solicitacoes/', params)
        self.assertEqual(response.context['paginator'].count, 32)
        self.assertEqual(response.context['stat_counts']['all'], 34)
        self.assertEqual(response.context['stat_counts']['cancelada'], 32)
        self.assertEqual([row.id for row in response.context['object_list']], list(range(107, 100, -1)))
        canceled = next(column for column in response.context['columns'] if column['status'] == 'cancelada')
        self.assertEqual(len(canceled['bookings']), 7)
        html = response.content.decode()
        tab_html = html.split('aria-label="Filtrar solicitações por situação"')[1].split('</nav>')[0]
        self.assertNotIn('page=', tab_html)
        self.assertIn('q=Pedido', tab_html)
        self.assertIn('mes=2026-11', tab_html)
        self.assertContains(response, 'status=cancelada&amp;q=Pedido&amp;mes=2026-11&amp;page=1')

    def test_decisions_move_cards_to_new_column_in_all_tab(self):
        self.stub.state['reservas'] = [self.reservation(101), self.reservation(102)]
        self.client.post('/agenda/solicitacoes/101/decidir/', {'decisao': 'confirmar'})
        response = self.client.post('/agenda/solicitacoes/102/decidir/', {'decisao': 'cancelar'}, follow=True)
        columns = {column['status']: [row.id for row in column['bookings']] for column in response.context['columns']}
        self.assertEqual(columns, {'pendente': [], 'cancelada': [102], 'recusada': []})
        self.assertEqual(response.context['stat_counts']['pendente'], 0)
        self.assertNotContains(response, 'value="confirmar"')
        self.assertNotContains(response, 'value="cancelar"')
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertFalse(AgendaServico.objects.exists())
        self.assertFalse(AgendaEquipamento.objects.exists())

    def test_confirm_uses_remote_id_without_creating_local_booking(self):
        room = {**self.stub.state['sala'], 'id': 2, 'slug': 'segunda-sala'}
        self.stub.state.update(rooms=[room], reservas=[self.reservation(room=room)])
        response = self.client.post('/agenda/solicitacoes/101/decidir/',
                                    {'decisao': 'confirmar', 'q': 'Pedido', 'mes': '2026-11', 'status': 'pendente'})
        self.assertRedirects(response, '/agenda/solicitacoes/?q=Pedido&mes=2026-11&status=pendente', fetch_redirect_response=False)
        self.assertEqual(self.writes(), [('PATCH', '/api/v1/agendamentos/reservas/101/',
                                         {'status': 'confirmada'}, 'Bearer access-1')])
        self.assertContains(self.client.get('/agenda/solicitacoes/'), 'Reserva #101 confirmada no AgroHub.')
        self.assertEqual(self.stub.state['reservas'][0]['status'], 'confirmada')
        self.assertEqual((AgendaServico.objects.count(), EventoAgendamento.objects.count(), AgendaEquipamento.objects.count()),
                         (0, 0, 0))

    def test_cancel_posts_to_provider_and_reservation_disappears(self):
        self.stub.state['reservas'] = [self.reservation()]
        response = self.client.post('/agenda/solicitacoes/101/decidir/', {'decisao': 'cancelar', 'status': 'pendente'}, follow=True)
        self.assertContains(response, 'Reserva #101 cancelada no AgroHub.')
        self.assertEqual(response.context['paginator'].count, 0)
        self.assertEqual(self.writes(), [('POST', '/api/v1/agendamentos/reservas/101/cancelar/', {}, 'Bearer access-1')])

    def test_action_is_post_only_protected_by_csrf_and_admin_role(self):
        self.stub.state['reservas'] = [self.reservation()]
        url = '/agenda/solicitacoes/101/decidir/'
        self.assertEqual(self.client.get(url).status_code, 405)
        secure = Client(enforce_csrf_checks=True)
        secure.cookies = self.client.cookies.copy()
        self.assertEqual(secure.post(url, {'decisao': 'confirmar'}).status_code, 403)
        secure.get('/agenda/solicitacoes/')
        response = secure.post(url, {'decisao': 'confirmar'}, HTTP_X_CSRFTOKEN=secure.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        before = len(self.writes())
        for roles in (['staff'], ['student'], []):
            self.login(roles)
            self.assertEqual(self.client.post(url, {'decisao': 'confirmar'}).status_code, 403)
        local = get_user_model().objects.create_superuser('admin-local')
        self.client.force_login(local)
        self.assertEqual(self.client.post(url, {'decisao': 'confirmar'}).status_code, 403)
        self.assertEqual(len(self.writes()), before)

    def test_action_rejects_forged_fields_invalid_decision_month_and_id(self):
        self.stub.state['reservas'] = [self.reservation()]
        url = '/agenda/solicitacoes/101/decidir/'
        for payload in ({}, {'decisao': 'aprovar'}, {'decisao': 'confirmar', 'sala': 'outra'},
                        {'decisao': 'confirmar', 'status': 'confirmada'},
                        {'decisao': ['confirmar', 'cancelar']}, {'decisao': 'confirmar', 'mes': '2026-99'}):
            self.assertEqual(self.client.post(url, payload).status_code, 400)
        for pk in (0, 9223372036854775808):
            self.assertEqual(self.client.post(f'/agenda/solicitacoes/{pk}/decidir/', {'decisao': 'confirmar'}).status_code, 400)
        self.assertFalse(self.listing_requests())

    def test_foreign_or_stale_reservation_cannot_be_decided(self):
        url = '/agenda/solicitacoes/101/decidir/'
        foreign = {**self.stub.state['sala'], 'id': 3, 'slug': 'outra-sala', 'site_code': 'agrohub'}
        self.stub.state.update(rooms=[self.stub.state['sala'], foreign], reservas=[self.reservation(room=foreign)])
        self.assertEqual(self.client.post(url, {'decisao': 'confirmar'}).status_code, 403)
        for status in ('confirmada', 'cancelada', 'recusada'):
            self.stub.state['reservas'] = [self.reservation(status=status)]
            self.assertContains(self.client.post(url, {'decisao': 'cancelar'}), 'não está mais pendente', status_code=409)
        self.assertFalse(self.writes())

    def test_provider_refusals_and_uncertain_result_do_not_claim_success_or_retry(self):
        url = '/agenda/solicitacoes/101/decidir/'
        self.stub.state['reservas'] = [self.reservation()]
        for upstream, status in ((400, 400), (403, 403), (404, 404), (422, 400), (503, 503)):
            self.stub.state['action_error'] = upstream
            response = self.client.post(url, {'decisao': 'confirmar'})
            self.assertEqual(response.status_code, status)
            self.assertContains(response, 'Voltar às solicitações', status_code=status)
        self.stub.state.update(action_error=None, action_uncertain=True)
        before = len(self.writes())
        self.assertContains(self.client.post(url, {'decisao': 'confirmar'}), 'Atualize as solicitações', status_code=503)
        self.assertEqual(len(self.writes()), before+1)
        self.assertEqual(self.stub.state['reservas'][0]['status'], 'confirmada')
        self.assertEqual(self.client.post(url, {'decisao': 'confirmar'}).status_code, 409)
        self.assertEqual(len(self.writes()), before+1)

    def test_malformed_detail_or_mutation_response_cannot_claim_success(self):
        url = '/agenda/solicitacoes/101/decidir/'
        for detail in ({}, {'id': True, 'sala': {}}, self.reservation(status='unexpected'), self.reservation(status=[])):
            self.stub.state.update(reservas=[self.reservation()], detail_reply=detail)
            self.assertEqual(self.client.post(url, {'decisao': 'confirmar'}).status_code, 503)
        self.assertFalse(self.writes())
        for reply in ({}, self.reservation(id=102, status='confirmada'),
                      self.reservation(status='pendente'), self.reservation(status='confirmada', sala={'id': 3})):
            self.stub.state.update(reservas=[self.reservation()], detail_reply=None, action_reply=reply)
            self.assertEqual(self.client.post(url, {'decisao': 'confirmar'}).status_code, 503)
        self.assertFalse(AgendaServico.objects.exists())

    def test_action_refreshes_credentials_and_uses_renewed_bearer(self):
        self.stub.state.update(reservas=[self.reservation()], expired=True)
        response = self.client.post('/agenda/solicitacoes/101/decidir/', {'decisao': 'cancelar'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.writes()[0][3], 'Bearer access-2')

    def test_refuse_patches_status_and_keeps_request_out_of_agenda(self):
        self.stub.state['reservas'] = [self.reservation()]
        response = self.client.post('/agenda/solicitacoes/101/decidir/', {'decisao': 'recusar'}, follow=True)
        self.assertContains(response, 'Reserva #101 recusada no AgroHub.')
        self.assertEqual(self.writes(), [('PATCH', '/api/v1/agendamentos/reservas/101/', {'status': 'recusada'}, 'Bearer access-1')])
        self.assertEqual(response.context['stat_counts']['recusada'], 1)
        self.assertNotContains(response, 'value="recusar"')
        refused = self.client.get('/agenda/solicitacoes/', {'status': 'recusada', 'q': 'Pedido', 'mes': '2026-11'})
        self.assertEqual(refused.context['selected_status'], 'recusada')
        self.assertEqual([row.id for row in refused.context['object_list']], [101])
        self.assertContains(refused, 'aria-label="Recusadas"><h2>Recusadas')
        self.assertNotContains(refused, 'aria-label="Pendentes"><h2>Pendentes')
        self.assertContains(refused, 'name="status" value="recusada"')
        self.assertContains(self.client.get('/agenda/solicitacoes/', {'status': 'recusada', 'q': 'Sem resultado'}),
                            'Nenhuma reserva recusada no AgroHub')
        self.assertFalse(AgendaServico.objects.exists())

    def test_confirmed_visits_appear_in_calendar_and_remote_details_without_persistence(self):
        self.stub.state['reservas'] = [self.reservation(status='confirmada')]
        for _ in range(2):
            self.client.get('/agenda/solicitacoes/', {'q': 'Filtro sem resultado'})
        response = self.client.get('/agenda/', {'mes': '2026-11', 'q': 'Pessoa externa'})
        self.assertEqual(response.context['paginator'].count, 1)
        days = [day for week in response.context['weeks'] for day in week if day['date'].isoformat() == '2026-11-10']
        self.assertEqual(days[0]['count'], 1)
        self.assertContains(response, 'Pedido do monólito')
        self.assertContains(response, '/agenda/visitas/101/')
        detail = self.client.get('/agenda/visitas/101/')
        self.assertContains(detail, 'Pessoa externa')
        self.assertContains(detail, 'Pedido do monólito')
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))
        self.assertFalse(self.writes())

    def test_agenda_reads_current_provider_changes_and_never_displays_stale_visits(self):
        self.stub.state['reservas'] = [self.reservation(status='confirmada')]
        self.assertContains(self.client.get('/agenda/', {'mes': '2026-11'}), 'Pedido do monólito')
        self.stub.state['reservas'][0].update(inicio='2026-11-10T11:00:00-03:00', fim='2026-11-10T12:00:00-03:00',
                                             titulo='Título atualizado', quantidade_pessoas=7)
        response = self.client.get('/agenda/', {'mes': '2026-11'})
        self.assertContains(response, 'Título atualizado')
        self.assertEqual(response.context['object_list'][0].quantidade_pessoas, 7)
        self.stub.state['reservas'][0]['status'] = 'cancelada'
        self.assertEqual(self.client.get('/agenda/', {'mes': '2026-11'}).context['paginator'].count, 0)
        self.stub.state['listing_error'] = 503
        self.assertContains(self.client.get('/agenda/', {'mes': '2026-11'}), 'Visitas indisponíveis')
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))
        self.assertFalse(self.writes())

    def test_provider_failure_keeps_local_bookings_accessible_without_claiming_zero_visits(self):
        user = get_user_model().objects.get(agrohub_id=42)
        local = AgendaServico.objects.create(servico=Servico.objects.first(), motivo='Pedido local',
            inicio='2026-11-10T12:00:00Z', fim='2026-11-10T13:00:00Z', criado_por=user)
        self.stub.state['listing_error'] = 503
        response = self.client.get('/agenda/', {'mes': '2026-11'})
        self.assertContains(response, 'Visitas indisponíveis')
        self.assertContains(response, local.get_absolute_url())
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (1, 0, 0))

    def test_invalid_or_incomplete_remote_snapshot_does_not_write_local_records(self):
        self.stub.state.update(ignore_filters=True, reservas=[self.reservation(status='confirmada'), self.reservation(102, status=[])])
        self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 503)
        self.stub.state.update(reservas=[self.reservation(status='confirmada')], listing_error=503)
        self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 503)
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))

    def test_other_inovalab_rooms_are_displayed_without_local_conflict_or_writes(self):
        room = {**self.stub.state['sala'], 'id': 2, 'slug': 'segunda-sala'}
        self.stub.state.update(rooms=[room], reservas=[self.reservation(room=room, status='confirmada')])
        response = self.client.get('/agenda/', {'mes': '2026-11'})
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertEqual(response.context['object_list'][0].sala_id, 2)
        self.assertFalse(self.writes())
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count()), (0, 0))

    def test_dashboard_combines_confirmed_remote_visits_and_local_bookings(self):
        from unittest.mock import patch
        from datetime import datetime
        self.stub.state['reservas'] = [self.reservation(status='confirmada')]
        from core.dashboard import dashboard_context
        with patch('core.views.dashboard_context', side_effect=lambda actor, **kwargs: dashboard_context(actor, now=datetime.fromisoformat('2026-11-10T08:00:00-03:00'), **kwargs)):
            response = self.client.get('/index/')
        self.assertContains(response, '/agenda/visitas/101/')
        self.assertContains(response, 'Pedido do monólito')
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))
