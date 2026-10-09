from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.core.exceptions import PermissionDenied, ValidationError
from unittest.mock import patch

from inovalab_app.tests.agenda.helpers import make_booking
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.agenda.selectors import own_bookings, visible_bookings, visible_booking


NOW = datetime(2026, 10, 8, 12, tzinfo=ZoneInfo('America/Sao_Paulo'))


class ExecutionPolicyTests(SimpleTestCase):
    def service(self, facts, **changes):
        from inovalab_app.agenda.execution import classify_execution
        return classify_execution(**dict(category='servico', situation='confirmado', cancelled=False,
            now=changes.pop('now', NOW), deadline=changes.pop('deadline', NOW), tasks=facts, **changes))

    def test_service_phases_and_deadline_boundaries(self):
        from inovalab_app.agenda.execution import TaskExecutionFacts
        empty = TaskExecutionFacts(0, 0, 0, None)
        self.assertEqual(self.service(empty).estado, 'aguardando_inicio')
        self.assertFalse(self.service(empty).atrasado)
        self.assertTrue(self.service(empty, now=NOW + timedelta(seconds=1)).atrasado)
        self.assertEqual(self.service(TaskExecutionFacts(2, 1, 1, None)).estado, 'em_execucao')
        completed = self.service(TaskExecutionFacts(2, 0, 2, NOW))
        self.assertEqual((completed.estado, completed.atrasado, completed.concluido_com_atraso),
                         ('concluido', False, False))
        late = NOW + timedelta(seconds=1)
        completed = self.service(TaskExecutionFacts(2, 0, 2, late), now=late)
        self.assertEqual((completed.estado, completed.atrasado, completed.concluido_com_atraso),
                         ('concluido', False, True))
        self.assertEqual(completed.concluido_em, late)

    def test_visit_interval_and_realization_precedence(self):
        from inovalab_app.agenda.execution import classify_execution
        start, end = NOW.replace(hour=9), NOW.replace(hour=10)
        for instant, expected in [(start-timedelta(seconds=1), 'aguardando_inicio'),
                                  (start, 'em_execucao'), (end-timedelta(seconds=1), 'em_execucao'),
                                  (end, 'aguardando_encerramento'), (NOW, 'aguardando_encerramento')]:
            state = classify_execution(category='visita', situation='confirmado', cancelled=False,
                now=instant, start=start, end=end)
            self.assertEqual(state.estado, expected)
            self.assertFalse(state.atrasado)
        recorded = start + timedelta(minutes=15)
        state = classify_execution(category='visita', situation='confirmado', cancelled=False,
            now=recorded, start=start, end=end, realized_at=recorded)
        self.assertEqual((state.estado, state.concluido_em), ('concluido', recorded))

    def test_non_applicable_has_no_alerts(self):
        from inovalab_app.agenda.execution import classify_execution, TaskExecutionFacts
        for category, situation, cancelled in [('servico', 'pendente', False), ('servico', 'rejeitado', False),
                                               ('servico', 'confirmado', True), ('equipamento', 'confirmado', False)]:
            state = classify_execution(category=category, situation=situation, cancelled=cancelled,
                now=NOW, deadline=NOW-timedelta(days=1), tasks=TaskExecutionFacts(1, 1, 1, None))
            self.assertEqual((state.estado, state.atrasado, state.concluido_com_atraso),
                             ('nao_aplicavel', False, False))


class ExecutionReadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('execucao-admin')
        cls.owner = get_user_model().objects.create_user('execucao-titular', is_staff=True)
        cls.other = get_user_model().objects.create_user('execucao-outro', is_staff=True)

    def task(self, booking, status='demanda'):
        task = Tarefa.objects.create(agendamento_servico=booking, responsavel=self.owner, descricao='Privado',
            status=status, inicio=NOW-timedelta(hours=1) if status != 'demanda' else None,
            conclusao=NOW if status == 'concluido' else None)
        task.responsaveis.add(self.owner, self.other)
        return task

    def read(self, booking):
        return visible_booking(self.admin, 'servico', booking.pk, now=NOW+timedelta(seconds=1))

    def test_reopen_delete_relink_and_new_task_recompute_execution(self):
        booking = make_booking(actor=self.owner, prazo=NOW)
        first = self.task(booking, 'concluido')
        second = self.task(booking, 'concluido')
        self.assertEqual(self.read(booking).estado_execucao, 'concluido')
        Tarefa.objects.filter(pk=second.pk).update(status='demanda', conclusao=None)
        row = self.read(booking)
        self.assertEqual((row.estado_execucao, row.atrasado), ('em_execucao', True))
        Tarefa.objects.filter(pk=second.pk).update(excluida_em=NOW)
        self.assertEqual(self.read(booking).estado_execucao, 'concluido')
        third = self.task(booking)
        self.assertEqual(self.read(booking).estado_execucao, 'em_execucao')
        other = make_booking(actor=self.owner, prazo=NOW)
        Tarefa.objects.filter(pk=first.pk).update(agendamento_servico=other)
        self.assertEqual(self.read(booking).estado_execucao, 'aguardando_inicio')
        Tarefa.objects.filter(pk=third.pk).update(status='concluido', inicio=NOW, conclusao=NOW+timedelta(seconds=1))
        self.assertTrue(self.read(booking).concluido_com_atraso)
        booking.servico.prazo = NOW+timedelta(hours=1)
        booking.servico.save(update_fields=['prazo'])
        self.assertFalse(self.read(booking).concluido_com_atraso)

    def test_one_instant_and_queries_do_not_grow_per_card(self):
        first = make_booking(actor=self.owner, prazo=NOW)
        self.task(first)
        with CaptureQueriesContext(connection) as single:
            rows = visible_bookings(self.admin, now=NOW)
        for _ in range(29):
            self.task(make_booking(actor=self.owner, prazo=NOW))
        with patch('inovalab_app.agenda.selectors.timezone.now', side_effect=[NOW, NOW+timedelta(seconds=1)]):
            with CaptureQueriesContext(connection) as many:
                rows = visible_bookings(self.admin)
                self.assertEqual({row.estado_execucao for row in rows}, {'aguardando_inicio'})
                self.assertFalse(any(row.atrasado for row in rows))
        self.assertEqual(len(single), len(many))
        self.assertEqual(len(rows), 30)
        from inovalab_app.agenda.execution import execution_for
        self.assertTrue(execution_for(rows[0], now=NOW+timedelta(seconds=1)).atrasado)

    def test_personal_reads_never_expose_foreign_tasks(self):
        from inovalab_app.agenda.selectors import management_bookings
        own = make_booking(actor=self.owner, prazo=NOW)
        foreign = make_booking(actor=self.other, prazo=NOW)
        self.task(own, 'concluido')
        self.task(foreign)
        self.assertEqual([row.pk for row in own_bookings(self.owner, now=NOW)], [own.pk])
        row = visible_booking(self.owner, 'servico', own.pk, now=NOW)
        self.assertEqual(row.estado_execucao, 'concluido')
        own.refresh_from_db()
        self.assertEqual((own.versao, own.eventos.count()), (1, 0))
        with self.assertRaises(PermissionDenied):
            management_bookings(self.owner)

    def test_execution_filters_keep_non_applicable_only_in_all(self):
        from inovalab_app.agenda.execution import filter_execution
        make_booking(actor=self.owner, prazo=NOW, situacao='pendente')
        booking = make_booking(actor=self.owner, prazo=NOW)
        rows = visible_bookings(self.admin, now=NOW+timedelta(seconds=1))
        self.assertEqual(len(filter_execution(rows)), 2)
        self.assertEqual([row.pk for row in filter_execution(rows, 'atrasado')], [booking.pk])
        self.assertEqual([row.pk for row in filter_execution(rows, 'aguardando_inicio')], [booking.pk])
        with self.assertRaises(ValidationError):
            filter_execution(rows, 'inventado')
