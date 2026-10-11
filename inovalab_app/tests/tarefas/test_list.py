from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.services import set_task_status, save_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskListTests(TaskFixtures, TestCase):
    def test_board_cutoff_is_inclusive_counts_match_and_list_keeps_old_tasks(self):
        now = timezone.now()
        set_task_status(actor=self.admin, task_id=self.mine.pk, status='concluido', expected_version=1)
        set_task_status(actor=self.admin, task_id=self.theirs.pk, status='concluido', expected_version=1)
        Tarefa.objects.filter(pk=self.mine.pk).update(conclusao=now - timedelta(days=7))
        Tarefa.objects.filter(pk=self.theirs.pk).update(conclusao=now - timedelta(days=7, microseconds=1))
        self.client.force_login(self.admin)
        with patch('inovalab_app.tarefas.views.timezone.now', return_value=now):
            response = self.client.get('/tarefas/', {'status': 'concluido'})
        self.assertEqual([task.pk for task in response.context['object_list']], [self.mine.pk])
        self.assertEqual(response.context['stat_counts']['concluido'], 1)
        self.assertEqual(response.context['columns'][-1]['count'], 1)
        self.assertEqual(self.client.get('/tarefas/lista/').context['paginator'].count, 2)

    def test_period_filters_use_conclusion_start_and_creation_and_preserve_access(self):
        self.client.force_login(self.owner)
        date = timezone.localdate().isoformat()
        response = self.client.get('/tarefas/lista/', {'de': date, 'ate': date, 'responsavel': self.owner.pk})
        self.assertEqual([task.pk for task in response.context['object_list']], [self.mine.pk])
        self.assertNotContains(response, self.theirs.descricao)
        self.assertNotContains(response, f'<option value="{self.other.pk}">')
        response = self.client.get('/tarefas/lista/', {'responsavel': self.other.pk})
        self.assertEqual(response.context['paginator'].count, 0)
        set_task_status(actor=self.admin, task_id=self.mine.pk, status='concluido', expected_version=1)
        Tarefa.objects.filter(pk=self.mine.pk).update(conclusao=timezone.now() - timedelta(days=20))
        response = self.client.get('/tarefas/lista/', {'de': date})
        self.assertEqual(response.context['paginator'].count, 0)

    def test_invalid_dates_have_errors_and_pagination_keeps_filters(self):
        self.client.force_login(self.admin)
        for data in ({'de': 'abc'}, {'de': '2026-10-12', 'ate': '2026-10-11'}):
            response = self.client.get('/tarefas/lista/', data)
            self.assertTrue(response.context['filter_form'].errors)
            self.assertEqual(response.context['paginator'].count, 0)
        for _ in range(26):
            save_task(actor=self.admin, data={'agendamento_servico': self.booking,
                'responsavel': self.owner, 'descricao': 'Busca paginada'})
        response = self.client.get('/tarefas/lista/', {'q': 'Busca paginada', 'responsavel': self.owner.pk})
        self.assertEqual(len(response.context['object_list']), 25)
        self.assertContains(response, 'q=Busca+paginada')
        self.assertContains(response, f'responsavel={self.owner.pk}')
