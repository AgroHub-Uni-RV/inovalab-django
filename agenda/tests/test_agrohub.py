from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, TransactionTestCase, override_settings

from accounts.tests.agrohub_stub import PASSWORD, PROFILE
from agenda.models import Agendamento
from agenda.tests.agrohub_stub import ReservationsStub
from agenda.services import save_booking
from django.utils import timezone
from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import RequestFactory
from agenda.models import ReservaAgroHub
from agenda.agrohub import sync_reservation


class VisitAgroHubTests(TestCase):
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
        self.stub.reset()
        response = self.client.post('/', {'username': 'agro-ana', 'password': PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.user = get_user_model().objects.get(agrohub_id=42)

    def create(self, **data):
        return self.client.post('/agenda/novo/', {'categoria': 'visita', 'dia': '2026-11-10',
            'hora_inicio': '09:00', 'hora_termino': '10:00', **data})

    def writes(self, method='POST'):
        return [row for row in self.stub.state['requests'] if row[0] == method
                and row[1].startswith('/api/v1/agendamentos/reservas/')]

    def test_web_creation_registers_room_one_with_creator_token_and_local_pending(self):
        response = self.create()
        self.assertEqual(response.status_code, 302)
        booking = Agendamento.objects.get()
        self.assertEqual(booking.situacao, 'pendente')
        self.assertEqual(len(self.writes()), 1)
        sent = self.writes()[0]
        self.assertEqual(sent[3], 'Bearer access-1')
        self.assertEqual({key: sent[2][key] for key in ('sala', 'data', 'hora_inicio', 'hora_fim')},
            {'sala': 'laboratorio-inovalab', 'data': '2026-11-10', 'hora_inicio': '09:00:00', 'hora_fim': '10:00:00'})
        self.assertEqual(sent[2]['quantidade_pessoas'], 1)
        self.assertEqual(booking.reserva_agrohub.reserva_id, 101)
        self.assertContains(self.client.get(response.url), 'Laboratório InovaLab')

    def test_internal_api_creation_also_registers_room_one(self):
        response = self.client.post('/api/v1/agendamentos/', {'categoria': 'visita',
            'inicio': '2026-11-10T12:00:00Z', 'fim': '2026-11-10T13:00:00Z'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(response.json()['reserva_agrohub']['reserva_id'], 101)

    def test_provider_can_confirm_creation_without_changing_local_approval(self):
        self.stub.state['create_status'] = 'confirmada'
        self.create()
        booking = Agendamento.objects.get()
        self.assertEqual(booking.situacao, 'pendente')
        self.assertEqual(booking.reserva_agrohub.estado, 'registrada')
        self.assertEqual(booking.reserva_agrohub.status_remoto, 'confirmada')

    def test_write_response_without_id_is_reconciled_by_reference(self):
        self.stub.state['omit_id'] = True
        self.create()
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(Agendamento.objects.get().reserva_agrohub.reserva_id, 101)

    def test_remote_rejection_keeps_local_visit_and_shows_failure(self):
        self.stub.state['create_error'] = 400
        response = self.create()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Agendamento.objects.count(), 1)
        self.assertContains(self.client.get(response.url), 'não foi registrada no AgroHub')

    def test_local_confirmation_is_labelled_and_flash_does_not_claim_external_success(self):
        self.admin()
        self.stub.state['create_error'] = 400
        response = self.create()
        page = self.client.get(response.url)
        self.assertContains(page, 'Agendamento salvo no InovaLab.')
        self.assertContains(page, 'Situação no InovaLab:')
        self.assertContains(page, 'não foi registrada no AgroHub')
        self.assertNotContains(page, 'Operação registrada no AgroHub.')
        self.assertNotContains(page, 'Agendamento salvo no InovaLab. Confira a operação pendente no AgroHub.')
        self.assertContains(page, 'flash-messages warning')
        self.assertNotContains(page, 'Há uma operação aguardando confirmação no AgroHub.')

    def test_uncertain_create_is_found_without_a_second_post(self):
        self.stub.state['create_uncertain'] = True
        self.create()
        booking = Agendamento.objects.get()
        response = self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': booking.versao})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(booking.reserva_agrohub.reserva_id, 101)

    def test_invalid_local_period_never_calls_remote_reservations(self):
        self.assertEqual(self.create(hora_termino='08:00').status_code, 200)
        self.assertFalse(self.writes())
        self.assertFalse(Agendamento.objects.exists())

    def admin(self):
        self.user.groups.add(Group.objects.get_or_create(name='Administradores')[0])

    def test_accepted_create_with_temporarily_inaccessible_detail_is_not_repeated(self):
        self.stub.state['responses'][('GET', '/api/v1/agendamentos/reservas/101/')] = (404, {})
        self.create()
        booking = Agendamento.objects.get()
        self.assertEqual(booking.reserva_agrohub.estado, 'incerta')
        self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1})
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(Agendamento.objects.get().reserva_agrohub.reserva_id, 101)

    def test_known_rejection_can_be_retried_once_and_registered_retry_is_noop(self):
        self.stub.state['create_error'] = 400
        self.create()
        booking = Agendamento.objects.get()
        self.stub.state['create_error'] = None
        for _ in range(2):
            self.assertEqual(self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1}).status_code, 302)
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(len(self.stub.state['reservas']), 1)

    def test_missing_in_uncertain_result_never_resends_create_or_allows_edit(self):
        self.stub.state['create_uncertain'] = True
        self.create()
        self.stub.state['reservas'] = []
        booking = Agendamento.objects.get()
        self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1})
        self.assertEqual(len(self.writes()), 1)
        self.admin()
        response = self.client.patch(f'/api/v1/agendamentos/{booking.pk}/',
            {'fim': '2026-11-10T14:00:00Z', 'versao': 1}, content_type='application/json')
        self.assertEqual(response.status_code, 409)
        booking.refresh_from_db()
        self.assertEqual(booking.versao, 1)

    def test_admin_review_update_and_cancel_keep_same_remote_id(self):
        self.create()
        booking = Agendamento.objects.get()
        self.admin()
        self.assertEqual(self.client.post(f'/agenda/{booking.pk}/avaliar/', {'decisao': 'aprovar', 'versao': 1}).status_code, 302)
        self.assertEqual(self.stub.state['reservas'][0]['status'], 'confirmada')
        response = self.client.patch(f'/api/v1/agendamentos/{booking.pk}/',
            {'fim': '2026-11-10T14:00:00Z', 'versao': 2}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.stub.state['reservas'][0]['hora_fim'], '11:00:00')
        response = self.client.delete(f'/api/v1/agendamentos/{booking.pk}/', {'versao': 3}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.stub.state['reservas'][0]['status'], 'cancelada')
        self.assertEqual(len(self.stub.state['reservas']), 1)
        self.assertEqual(len(self.writes('PATCH')), 2)
        self.assertEqual(self.client.get(f'/agenda/{booking.pk}/agrohub/').status_code, 200)

    def test_cancel_failure_remains_visible_and_retry_uses_cancel_route(self):
        self.create()
        booking = Agendamento.objects.get()
        self.admin()
        route = '/api/v1/agendamentos/reservas/101/cancelar/'
        self.stub.state['responses'][('POST', route)] = (403, {})
        response = self.client.post(f'/agenda/{booking.pk}/cancelar/', {'versao': 1})
        self.assertEqual(response.url, f'/agenda/{booking.pk}/agrohub/')
        self.assertContains(self.client.get(response.url), 'ainda não foi confirmada no AgroHub')
        del self.stub.state['responses'][('POST', route)]
        self.client.post(response.url, {'versao': 2})
        self.assertEqual(self.stub.state['reservas'][0]['status'], 'cancelada')
        self.assertEqual(len(self.stub.state['reservas']), 1)

    def test_rejection_cancels_remote_reservation(self):
        self.create()
        self.admin()
        booking = Agendamento.objects.get()
        self.client.post(f'/agenda/{booking.pk}/avaliar/', {'decisao': 'rejeitar', 'versao': 1})
        self.assertEqual(self.stub.state['reservas'][0]['status'], 'cancelada')

    def test_room_must_be_active_and_have_id_one(self):
        for changes in ({'id': 2}, {'ativa': False}, {'site_code': 'outro'}):
            self.stub.reset()
            self.stub.state['sala'].update(changes)
            self.create()
        self.assertFalse(self.writes())

    def test_wrong_remote_room_never_binds_and_retry_does_not_create(self):
        self.stub.state['responses'][('GET', '/api/v1/agendamentos/reservas/101/')] = (200, {'id': 101, 'sala': {'id': 2}})
        self.create()
        booking = Agendamento.objects.get()
        self.assertIsNone(booking.reserva_agrohub.reserva_id)
        self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1})
        self.assertEqual(len(self.writes()), 1)

    def test_origin_change_and_stale_version_never_write(self):
        self.stub.state['create_error'] = 400
        self.create()
        booking = Agendamento.objects.get()
        self.stub.state['responses'][('GET', '/api/v1/outro/accounts/me/')] = (200, PROFILE)
        with override_settings(AGROHUB_API_BASE_URL=self.stub.url+'outro/'):
            response = self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1})
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 2}).status_code, 409)
        self.assertEqual(len(self.writes()), 1)

    def test_owner_only_retry_csrf_and_private_metadata(self):
        self.stub.state['create_error'] = 400
        response = self.client.post('/api/v1/agendamentos/', {'categoria': 'visita',
            'inicio': '2026-11-10T12:00:00Z', 'fim': '2026-11-10T13:00:00Z'}, content_type='application/json')
        booking = Agendamento.objects.get()
        self.assertEqual(set(response.json()['reserva_agrohub']), {'reserva_id', 'estado', 'status', 'mensagem'})
        other = get_user_model().objects.create_user(username='other', agrohub_id=43)
        # Service identity check is independent of the provider middleware.
        from agenda.agrohub import can_sync
        self.assertFalse(can_sync(other, booking.reserva_agrohub))
        guarded = Client(enforce_csrf_checks=True)
        guarded.cookies = self.client.cookies
        self.assertEqual(guarded.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1}).status_code, 403)
        self.assertEqual(guarded.post(f'/api/v1/agendamentos/{booking.pk}/agrohub/', {'versao': 1}, content_type='application/json').status_code, 403)

    def test_historical_visit_without_link_is_not_exported_on_review(self):
        start = timezone.now()+timedelta(days=40)
        booking = save_booking(actor=self.user, data={'categoria': 'visita', 'inicio': start, 'fim': start+timedelta(hours=1)})
        booking.reserva_agrohub.delete()
        self.admin()
        self.client.post(f'/agenda/{booking.pk}/avaliar/', {'decisao': 'aprovar', 'versao': 1})
        self.assertFalse(self.writes())
        self.assertFalse(hasattr(Agendamento.objects.get(), 'reserva_agrohub'))

    def test_interrupted_room_lookup_can_resume_without_missing_slug(self):
        self.stub.state['sala']['ativa'] = False
        self.create()
        booking = Agendamento.objects.get()
        sync = booking.reserva_agrohub
        sync.estado = 'enviando'
        sync.ultima_tentativa = timezone.now()-timedelta(minutes=3)
        sync.save()
        self.stub.state['sala']['ativa'] = True
        self.assertEqual(self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1}).status_code, 302)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(Agendamento.objects.get().reserva_agrohub.reserva_id, 101)

    def test_get_result_does_not_write_and_recent_inflight_post_is_not_repeated(self):
        self.stub.state['create_error'] = 400
        self.create()
        booking = Agendamento.objects.get()
        sync = booking.reserva_agrohub
        sync.estado, sync.ultima_tentativa = 'enviando', timezone.now()
        sync.save()
        self.client.get(f'/agenda/{booking.pk}/agrohub/')
        self.client.post(f'/agenda/{booking.pk}/agrohub/', {'versao': 1})
        self.assertEqual(len(self.writes()), 1)

    def test_token_refresh_during_creation_rechecks_identity_and_replays_same_payload(self):
        self.stub.state['responses'][('POST', '/api/v1/agendamentos/reservas/')] = (401, {})
        self.create()
        posts = self.writes()
        self.assertEqual([row[3] for row in posts], ['Bearer access-1', 'Bearer access-2'])
        self.assertEqual(posts[0][2], posts[1][2])
        self.assertEqual(Agendamento.objects.get().reserva_agrohub.estado, 'falha')

    def test_foreign_account_cannot_read_or_retry_link(self):
        self.create()
        booking = Agendamento.objects.get()
        self.user.agrohub_id = 43
        self.user.save(update_fields=['agrohub_id'])
        self.client.post('/sair/')
        self.client.post('/', {'username': 'agro-ana', 'password': PASSWORD})
        self.assertEqual(self.client.get(f'/agenda/{booking.pk}/agrohub/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/v1/agendamentos/{booking.pk}/agrohub/', {'versao': 1}, content_type='application/json').status_code, 404)

    def request(self, user=None):
        request = RequestFactory().post('/')
        request.user, request.session = user or self.user, self.client.session
        return request

    def test_worker_that_loses_claim_during_room_lookup_cannot_post(self):
        self.stub.state['sala']['ativa'] = False
        self.create()
        booking = Agendamento.objects.get()
        self.stub.state['sala']['ativa'] = True
        from agenda.agrohub import _room
        def interrupted(request):
            ReservaAgroHub.objects.filter(agendamento=booking).update(ultima_tentativa=timezone.now()-timedelta(minutes=3))
            with patch('agenda.agrohub._room', wraps=_room):
                sync_reservation(self.request(), booking)
            return 'laboratorio-inovalab'
        with patch('agenda.agrohub._room', side_effect=interrupted):
            sync_reservation(self.request(), booking)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(Agendamento.objects.get().reserva_agrohub.reserva_id, 101)

    def test_other_admin_can_approve_known_failed_creation_without_post_as_admin(self):
        self.stub.state['create_error'] = 400
        self.create()
        admin = get_user_model().objects.create_user(username='admin43', agrohub_id=43, is_superuser=True)
        from agenda.services import review_booking
        saved = review_booking(actor=admin, booking_id=Agendamento.objects.get().pk, expected_version=1,
            decision='aprovar', agrohub_request=self.request(admin))
        self.assertEqual(saved.situacao, 'confirmado')
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(saved.reserva_agrohub.payload['status'], 'confirmada')

    def test_malformed_status_is_visible_failure_not_server_error(self):
        self.create()
        booking = Agendamento.objects.get()
        self.stub.state['reservas'][0]['status'] = []
        self.admin()
        response = self.client.patch(f'/api/v1/agendamentos/{booking.pk}/',
            {'fim': '2026-11-10T14:00:00Z', 'versao': 1}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['reserva_agrohub']['estado'], 'falha')

    def test_uncertain_patch_blocks_edits_and_retry_only_reads_existing_result(self):
        self.create()
        booking = Agendamento.objects.get()
        self.admin()
        self.stub.state['patch_uncertain'] = True
        response = self.client.patch(f'/api/v1/agendamentos/{booking.pk}/',
            {'fim': '2026-11-10T14:00:00Z', 'versao': 1}, content_type='application/json')
        self.assertEqual(response.json()['reserva_agrohub']['estado'], 'incerta')
        response = self.client.patch(f'/api/v1/agendamentos/{booking.pk}/',
            {'fim': '2026-11-10T15:00:00Z', 'versao': 2}, content_type='application/json')
        self.assertEqual(response.status_code, 409)
        response = self.client.post(f'/api/v1/agendamentos/{booking.pk}/agrohub/', {'versao': 2}, content_type='application/json')
        self.assertEqual(response.json()['estado'], 'registrada')
        self.assertEqual(len(self.writes('PATCH')), 1)

    def test_resources_are_not_exported_but_conversion_to_visit_registers_room(self):
        from catalogo.models import Servico
        self.admin()
        service = Servico.objects.create(nome='Teste de conversão')
        response = self.client.post('/api/v1/agendamentos/', {'categoria': 'servico', 'objeto': service.pk,
            'motivo': 'Teste', 'inicio': '2026-11-10T12:00:00Z', 'fim': '2026-11-10T13:00:00Z'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(self.writes())
        booking = Agendamento.objects.get()
        response = self.client.patch(f'/api/v1/agendamentos/{booking.pk}/', {'categoria': 'visita', 'versao': 1}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.writes()), 1)
        response = self.client.patch(f'/api/v1/agendamentos/{booking.pk}/', {'categoria': 'servico',
            'objeto': service.pk, 'motivo': 'Conversão', 'versao': 2}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.stub.state['reservas'][0]['status'], 'cancelada')


class VisitAgroHubConcurrencyTests(TransactionTestCase):
    def test_live_patch_holds_lock_against_expired_claim_takeover(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import connections
        from agenda.agrohub import _request
        from agenda.services import BookingConflict

        stub = ReservationsStub()
        entered, release = Event(), Event()
        try:
            with override_settings(AGROHUB_API_BASE_URL=stub.url, DEBUG=True):
                user = get_user_model().objects.create_user(username='agro-ana', agrohub_id=42, is_superuser=True)
                request = RequestFactory().post('/')
                request.user = user
                request.session = {'agrohub_credentials': {'user_id': 42, 'access': 'access-1', 'refresh': 'refresh-1'}}
                start = timezone.make_aware(datetime(2026, 11, 10, 9))
                booking = save_booking(actor=user, data={'categoria': 'visita', 'inicio': start,
                    'fim': start+timedelta(hours=1)}, agrohub_request=request)
                save_booking(actor=user, booking_id=booking.pk, expected_version=1, data={'fim': start+timedelta(hours=2)})
                booking.refresh_from_db()
                def paused(req, method, route, **kwargs):
                    if method == 'PATCH':
                        entered.set()
                        if not release.wait(10):
                            raise RuntimeError('A verificação de concorrência não liberou o PATCH.')
                    return _request(req, method, route, **kwargs)
                def worker():
                    try:
                        return sync_reservation(request, booking)
                    finally:
                        connections.close_all()
                with patch('agenda.agrohub._request', side_effect=paused), ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(worker)
                    try:
                        self.assertTrue(entered.wait(10))
                        with patch('agenda.agrohub.timezone.now', return_value=timezone.now()+timedelta(minutes=3)):
                            with self.assertRaises(BookingConflict):
                                sync_reservation(request, booking)
                        self.assertEqual(len([r for r in stub.state['requests'] if r[0] == 'PATCH']), 0)
                    finally:
                        release.set()
                    self.assertEqual(future.result(timeout=10).estado, 'registrada')
                self.assertEqual(stub.state['reservas'][0]['hora_fim'], '11:00:00')
        finally:
            stub.close()
