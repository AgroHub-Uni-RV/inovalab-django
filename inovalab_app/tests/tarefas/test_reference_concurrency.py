from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.db.models.query import QuerySet
from django.test import TransactionTestCase
from inovalab_app.agenda.models import AgendaServico
from inovalab_app.agenda.services import BookingConflict, cancel_booking, save_booking
from inovalab_app.tarefas.services import save_task
from inovalab_app.tests.agenda.helpers import service_data


class TaskReferenceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser('gestor-concorrencia-tarefa')
        self.booking = save_booking(actor=self.actor, data=service_data())
        self.payload = {'agendamento_servico': self.booking, 'responsavel': self.actor, 'descricao': 'Tarefa'}

    def test_reference_validation_and_first_write_share_transaction(self):
        original = QuerySet.exists
        validation_states = []
        statements = []
        def exists(query):
            if query.model is AgendaServico:
                validation_states.append(connection.in_atomic_block)
            return original(query)
        def capture(execute, sql, params, many, context):
            if connection.in_atomic_block and sql != 'BEGIN':
                statements.append(sql)
            return execute(sql, params, many, context)
        with patch.object(QuerySet, 'exists', exists), connection.execute_wrapper(capture):
            save_task(actor=self.actor, data=self.payload)
        self.assertTrue(validation_states)
        self.assertTrue(all(validation_states), validation_states)
        self.assertTrue(statements[0].startswith('UPDATE'), statements[0])

    def test_cancel_between_validation_and_insert_cannot_commit_invalid_new_assignment(self):
        if connection.vendor != 'sqlite':
            self.skipTest('Interleaving com conflito imediato de escrita no SQLite.')
        original = QuerySet.exists
        attempts = []
        def cancel():
            try:
                return cancel_booking(actor=self.actor, category='servico', booking_id=self.booking.pk, expected_version=1)
            except BookingConflict as error:
                return error
            finally:
                connections.close_all()
        def exists(query):
            result = original(query)
            if query.model is AgendaServico and not attempts:
                attempts.append(None)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    attempts[0] = pool.submit(cancel).result(timeout=10)
            return result
        with patch.object(QuerySet, 'exists', exists):
            try:
                task = save_task(actor=self.actor, data=self.payload)
            except ValidationError:
                task = None
        self.assertFalse(task is not None and isinstance(attempts[0], AgendaServico),
                         'Tarefa criada depois de cancelamento confirmado entre validação e gravação.')
