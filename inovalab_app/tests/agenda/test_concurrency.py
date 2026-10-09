from inovalab_app.tests.agenda.helpers import service_data
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, datetime
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from inovalab_app.agenda.models import AgendaEquipamento, AgendaServico, AgendaVisita, EventoAgendamento
from inovalab_app.agenda.services import BookingConflict, review_booking, save_booking
from inovalab_app.catalogo.models import Servico, Equipamento


class BookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('gestor', is_superuser=True)
        self.data = service_data()

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
            results = list(executor.map(worker, (0, 1)))
        # Shared-memory SQLite can reject both writes while readers finish. Retry once
        # after closing the worker connections, preserving version/overlap assertions.
        if all(isinstance(result, BookingConflict) and result.code == 'agenda_ocupada' for result in results):
            results[0] = operation(0)
        return results

    def test_parallel_service_requests_are_independent_and_can_share_deadline(self):
        results = self.run_parallel(lambda index: save_booking(actor=self.admin, data={**self.data, 'descricao': str(index)}))
        for index, result in enumerate(results):
            if isinstance(result, BookingConflict):
                self.assertEqual(result.code, 'agenda_ocupada')
                save_booking(actor=self.admin, data={**self.data, 'descricao': str(index)})
        self.assertEqual((AgendaServico.objects.count(), Servico.objects.count(), EventoAgendamento.objects.count()), (2, 2, 2))

    def test_equipment_requests_are_rejected_without_booking_or_event(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, data={'categoria': 'equipamento'})
        self.assertEqual((AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0))

    def test_parallel_visits_in_empty_agenda_commit_only_one_booking_and_event(self):
        data = {'categoria': 'visita', 'quantidade_pessoas': 5, 'data': date(2099, 11, 10),
                'hora_inicio': time(9), 'hora_termino': time(10)}
        results = self.run_parallel(lambda index: save_booking(actor=self.admin, data=data))
        self.assertEqual(sum(isinstance(result, AgendaVisita) for result in results), 1)
        self.assertEqual(sum(isinstance(result, BookingConflict) for result in results), 1)
        self.assertEqual((AgendaVisita.objects.count(), EventoAgendamento.objects.count()), (1, 1))

    def test_parallel_visit_approvals_confirm_only_one_and_preserve_pending_request(self):
        user = get_user_model().objects.create_user('solicitante-local-visita', is_staff=True)
        data = {'categoria': 'visita', 'quantidade_pessoas': 5, 'data': date(2099, 11, 10),
                'hora_inicio': time(9), 'hora_termino': time(10)}
        bookings = [save_booking(actor=user, data=data) for _ in range(2)]
        results = self.run_parallel(lambda index: review_booking(actor=self.admin, category='visita',
            booking_id=bookings[index].pk, expected_version=1, decision='aprovar'))
        self.assertEqual(sum(isinstance(result, AgendaVisita) for result in results), 1)
        self.assertEqual(sum(isinstance(result, BookingConflict) for result in results), 1)
        self.assertEqual(AgendaVisita.objects.filter(situacao='confirmado').count(), 1)
        self.assertEqual(AgendaVisita.objects.filter(situacao='pendente').count(), 1)
        self.assertEqual(EventoAgendamento.objects.filter(acao='aprovar').count(), 1)

    def test_parallel_service_approvals_can_confirm_independent_requests(self):
        user = get_user_model().objects.create_user('solicitante-service', is_staff=True)
        bookings = [save_booking(actor=user, data=self.data) for _ in range(2)]
        results = self.run_parallel(lambda index: review_booking(actor=self.admin, category='servico',
            booking_id=bookings[index].pk, expected_version=1, decision='aprovar',
            task_data={'descricao': 'Executar serviço', 'responsaveis': [user]}))
        for index, result in enumerate(results):
            if isinstance(result, BookingConflict):
                self.assertEqual(result.code, 'agenda_ocupada')
                review_booking(actor=self.admin, category='servico', booking_id=bookings[index].pk,
                               expected_version=1, decision='aprovar',
                               task_data={'descricao': 'Executar serviço', 'responsaveis': [user]})
        self.assertEqual(AgendaServico.objects.filter(situacao='confirmado').count(), 2)
        self.assertEqual(EventoAgendamento.objects.filter(acao='aprovar').count(), 2)

    def test_parallel_edits_from_same_version_cannot_overwrite_or_duplicate_events(self):
        booking = save_booking(actor=self.admin, data=self.data)
        results = self.run_parallel(lambda index: save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk,
                                                             expected_version=1, data={'descricao': str(index)}))
        self.assertEqual(sum(isinstance(result, AgendaServico) for result in results), 1)
        booking.refresh_from_db()
        winner = next(result for result in results if isinstance(result, AgendaServico))
        self.assertEqual((booking.motivo, booking.versao, booking.eventos.count()), (winner.motivo, 2, 2))

    def test_stale_edit_does_not_modify_service_or_create_event(self):
        booking = save_booking(actor=self.admin, data=self.data)
        save_booking(actor=self.admin, category='servico', booking_id=booking.pk,
                     expected_version=1, data={'descricao': 'Revisado'})
        with self.assertRaises(BookingConflict):
            save_booking(actor=self.admin, category='servico', booking_id=booking.pk,
                         expected_version=1, data={'titulo': 'Não gravar'})
        booking.refresh_from_db()
        self.assertEqual((booking.servico.titulo, booking.motivo, booking.versao, booking.eventos.count()),
                         (self.data['titulo'], 'Revisado', 2, 2))



    def test_parallel_opposite_decisions_cannot_overwrite_each_other(self):
        user = get_user_model().objects.create_user('solicitante', is_staff=True)
        booking = save_booking(actor=user, data=self.data)
        results = self.run_parallel(lambda index: review_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk,
                                   expected_version=1, decision=('aprovar', 'rejeitar')[index],
                                   task_data={'descricao': 'Executar serviço', 'responsaveis': [user]}))
        self.assertEqual(sum(isinstance(result, AgendaServico) for result in results), 1)
        booking.refresh_from_db()
        self.assertEqual((booking.versao, booking.eventos.count()), (2, 2))

    def test_parallel_confirmations_of_same_service_create_only_one_task(self):
        booking = save_booking(actor=self.admin, data=self.data)
        results = self.run_parallel(lambda index: review_booking(actor=self.admin, category='servico',
            booking_id=booking.pk, expected_version=1, decision='aprovar',
            task_data={'descricao': f'Executar {index}', 'responsaveis': [self.admin]}))
        self.assertEqual(sum(isinstance(result, AgendaServico) for result in results), 1)
        self.assertEqual(sum(isinstance(result, BookingConflict) for result in results), 1)
        booking.refresh_from_db()
        self.assertEqual((booking.situacao, booking.versao, booking.tarefas.count(), booking.eventos.count()),
                         ('confirmado', 2, 1, 2))

    def test_parallel_realizations_record_once(self):
        from inovalab_app.agenda.services import mark_visit_realized
        booking = AgendaVisita.objects.create(quantidade_pessoas=2, data=date(2026, 10, 8),
            hora_inicio=time(9), hora_termino=time(10), criado_por=self.admin)
        with patch('django.utils.timezone.now', return_value=booking.inicio):
            results = self.run_parallel(lambda index: mark_visit_realized(actor=self.admin,
                booking_id=booking.pk, expected_version=1))
        self.assertEqual(sum(isinstance(row, AgendaVisita) for row in results), 1)
        booking.refresh_from_db()
        self.assertEqual((booking.versao, booking.eventos.filter(acao='realizar').count()), (2, 1))
        self.assertEqual(booking.realizada_em, booking.inicio)

    def test_parallel_realization_and_edit_cannot_overwrite(self):
        from inovalab_app.agenda.services import mark_visit_realized
        booking = AgendaVisita.objects.create(quantidade_pessoas=2, data=date(2026, 10, 8),
            hora_inicio=time(9), hora_termino=time(10), criado_por=self.admin)
        with patch('django.utils.timezone.now', return_value=booking.inicio):
            results = self.run_parallel(lambda index: mark_visit_realized(actor=self.admin,
                booking_id=booking.pk, expected_version=1) if index == 0 else save_booking(
                actor=self.admin, category='visita', booking_id=booking.pk, expected_version=1,
                data={'observacoes': 'Edição concorrente'}))
        winners = [row for row in results if isinstance(row, AgendaVisita)]
        self.assertEqual(len(winners), 1)
        booking.refresh_from_db()
        self.assertEqual((booking.versao, booking.eventos.count()), (2, 1))
        self.assertEqual((booking.realizada_em, booking.observacoes),
                         (winners[0].realizada_em, winners[0].observacoes))
