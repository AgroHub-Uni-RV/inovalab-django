from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, connections
from django.test import TransactionTestCase

from agenda.models import Agendamento, EventoAgendamento
from agenda.services import BookingConflict, save_booking
from catalogo.models import Servico


class BookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('gestor', is_superuser=True)
        self.service = Servico.objects.create(nome='Serviço exclusivo')
        self.data = {'categoria': 'servico', 'objeto': self.service.pk, 'requerente': 'Ana', 'motivo': 'Protótipo',
                     'inicio': datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                     'fim': datetime.fromisoformat('2026-11-01T15:00:00-03:00')}

    def run_parallel(self, operation):
        barrier = Barrier(2)

        def worker(index):
            try:
                barrier.wait(timeout=10)
                return operation(index)
            except BookingConflict as error:
                return error
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(worker, (0, 1)))

    def test_parallel_overlapping_creations_commit_only_one_booking_and_event(self):
        results = self.run_parallel(lambda index: save_booking(actor=self.admin, data={**self.data, 'motivo': str(index)}))
        self.assertEqual(sum(isinstance(result, Agendamento) for result in results), 1)
        self.assertEqual(sum(isinstance(result, BookingConflict) for result in results), 1)
        self.assertEqual((Agendamento.objects.count(), EventoAgendamento.objects.count()), (1, 1))

    def test_parallel_edits_from_same_version_cannot_overwrite_or_duplicate_events(self):
        booking = save_booking(actor=self.admin, data=self.data)
        results = self.run_parallel(lambda index: save_booking(actor=self.admin, booking_id=booking.pk,
                                                             expected_version=1, data={'motivo': str(index)}))
        self.assertEqual(sum(isinstance(result, Agendamento) for result in results), 1)
        booking.refresh_from_db()
        winner = next(result for result in results if isinstance(result, Agendamento))
        self.assertEqual((booking.motivo, booking.versao, booking.eventos.count()), (winner.motivo, 2, 2))

    def test_target_write_precedes_any_read_inside_transaction(self):
        statements = []

        def capture(execute, sql, params, many, context):
            statements.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(capture):
            booking = save_booking(actor=self.admin, data=self.data)
        first = statements[statements.index('BEGIN') + 1]
        self.assertTrue(first.startswith('UPDATE "catalogo_servico"'), first)
        statements.clear()
        with connection.execute_wrapper(capture):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Revisado'})
        first = statements[statements.index('BEGIN') + 1]
        self.assertTrue(first.startswith('UPDATE "catalogo_servico"'), first)
