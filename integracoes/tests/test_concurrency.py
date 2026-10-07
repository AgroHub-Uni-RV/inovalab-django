from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico, EventoAgendamento
from agenda.services import BookingConflict
from catalogo.models import Servico
from integracoes.credentials import authenticate_token
from integracoes.models import PedidoIntegracao
from integracoes.services import create_client, receive_booking


class IntegrationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('gestor', is_superuser=True)
        self.client, self.token = create_client(actor=self.admin, name='AgroHub')
        self.principal = authenticate_token(self.token)
        self.service = Servico.objects.create(nome='Serviço exclusivo')
        self.other = Servico.objects.create(nome='Outro serviço')
        self.data = {'id_externo': '001', 'requerente_id': 'pessoa-45', 'requerente': 'Ana', 'motivo': 'Protótipo',
                     'categoria': 'servico', 'objeto': self.service.pk,
                     'inicio': datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                     'fim': datetime.fromisoformat('2026-11-01T15:00:00-03:00')}

    def parallel(self, data_for):
        barrier = Barrier(2)
        def worker(index):
            try:
                barrier.wait(timeout=10)
                return receive_booking(principal=self.principal, data=data_for(index))
            except BookingConflict as error:
                return error
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(worker, (0, 1)))

    def assert_single_booking(self, results):
        successes = [result for result in results if isinstance(result, tuple)]
        self.assertTrue(successes)
        self.assertEqual(len({result[0].pk for result in successes}), 1)
        self.assertEqual((PedidoIntegracao.objects.count(), (AgendaServico.objects.count() + AgendaEquipamento.objects.count()), EventoAgendamento.objects.count()), (1, 1, 1))

    def test_same_key_parallel_retries_have_one_receipt_booking_and_event(self):
        self.assert_single_booking(self.parallel(lambda index: self.data))

    def test_same_key_with_different_targets_cannot_create_two_bookings(self):
        results = self.parallel(lambda index: {**self.data, 'objeto': self.service.pk if index == 0 else self.other.pk})
        self.assert_single_booking(results)
        self.assertEqual(sum(isinstance(result, BookingConflict) for result in results), 1)

    def test_different_keys_same_target_interval_cannot_bypass_agenda_exclusivity(self):
        results = self.parallel(lambda index: {**self.data, 'id_externo': str(index)})
        self.assert_single_booking(results)
        self.assertEqual(sum(isinstance(result, BookingConflict) for result in results), 1)

    def test_client_write_precedes_reading_request_key_in_new_and_replayed_request(self):
        statements = []
        def capture(execute, sql, params, many, context):
            statements.append(sql)
            return execute(sql, params, many, context)
        for _ in range(2):
            statements.clear()
            with connection.execute_wrapper(capture):
                receive_booking(principal=self.principal, data=self.data)
            first = statements[statements.index('BEGIN') + 1]
            self.assertTrue(first.startswith('UPDATE "integracoes_clienteintegracao"'), first)
