from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from inovalab_app.tarefas.services import TaskConflict, delete_task, set_task_status, save_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class ExecutionTimeTests(TaskFixtures, TestCase):
    def move(self, status, instant):
        with patch('inovalab_app.tarefas.services.timezone.now', return_value=instant):
            self.mine = set_task_status(actor=self.admin, task_id=self.mine.pk,
                expected_version=self.mine.versao, status=status)

    def test_counts_only_creation_and_resumes_across_rework_and_reload(self):
        start = timezone.now()
        self.assertEqual(self.mine.tempo_execucao, '00:00:00')
        self.move('criacao', start)
        self.assertEqual(self.mine.execution_seconds(start + timedelta(seconds=65)), 65)
        self.move('avaliacao', start + timedelta(seconds=65))
        self.mine.refresh_from_db()
        self.assertIsNone(self.mine.criacao_desde)
        self.assertEqual(self.mine.execution_seconds(start + timedelta(days=1)), 65)
        self.move('criacao', start + timedelta(hours=1))
        self.move('concluido', start + timedelta(hours=1, seconds=35))
        self.assertEqual(self.mine.tempo_execucao, '00:01:40')
        self.move('criacao', start + timedelta(days=1))
        self.move('demanda', start + timedelta(days=1, seconds=10))
        self.assertEqual(self.mine.tempo_execucao, '00:01:50')

    def test_edit_does_not_restart_interval_and_delete_stops_it(self):
        start = timezone.now()
        self.move('criacao', start)
        self.mine = save_task(actor=self.admin, task_id=self.mine.pk, expected_version=self.mine.versao,
                             data={'descricao': 'Edição enquanto executa'})
        self.assertEqual(self.mine.criacao_desde, start)
        with patch('inovalab_app.tarefas.services.timezone.now', return_value=start + timedelta(seconds=80)):
            task = delete_task(actor=self.admin, task_id=self.mine.pk, expected_version=self.mine.versao)
        self.assertIsNone(task.criacao_desde)
        self.assertEqual(task.execution_seconds(), 80)

    def test_stale_update_cannot_accumulate_twice(self):
        start = timezone.now()
        self.move('criacao', start)
        version = self.mine.versao
        self.move('avaliacao', start + timedelta(seconds=30))
        with self.assertRaises(TaskConflict):
            set_task_status(actor=self.admin, task_id=self.mine.pk, expected_version=version, status='avaliacao')
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.execution_seconds(), 30)

    def test_long_duration_does_not_wrap_at_24_hours_and_topbar_has_clock(self):
        self.mine.tempo_criacao = timedelta(hours=125, seconds=9)
        self.mine.save(update_fields=['tempo_criacao'])
        self.assertEqual(self.mine.tempo_execucao, '125:00:09')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(f'/tarefas/{self.mine.pk}/'), '125:00:09')
        self.assertContains(self.client.get(f'/tarefas/{self.mine.pk}/'), 'data-task-timer')

    def test_migration_reconstructs_multiple_intervals_from_history(self):
        start = timezone.now() - timedelta(days=2)
        for seconds, status in [(0, 'criacao'), (30, 'avaliacao'), (100, 'criacao'), (150, 'concluido')]:
            self.move(status, start + timedelta(seconds=seconds))
            self.mine.eventos.order_by('-pk').first().__class__.objects.filter(
                pk=self.mine.eventos.order_by('-pk').first().pk).update(instante=start + timedelta(seconds=seconds))
        self.mine.tempo_criacao = timedelta()
        self.mine.save(update_fields=['tempo_criacao'])
        migration = import_module('inovalab_app.migrations.0008_tempo_execucao_tarefas')
        migration.recover_intervals(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.execution_seconds(), 80)
