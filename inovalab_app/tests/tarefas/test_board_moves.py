from django.test import TestCase
from django.urls import reverse

from inovalab_app.tests.tarefas.helpers import TaskFixtures
from inovalab_app.tarefas.services import set_task_status


class BoardMovesTests(TaskFixtures, TestCase):
    def choices(self, actor):
        self.client.force_login(actor)
        response = self.client.get(reverse('tarefas:board'))
        task = next(task for column in response.context['columns'] for task in column['tasks']
                    if task.pk == self.mine.pk)
        self.assertTrue(hasattr(task, 'move_choices'), 'O quadro deve oferecer destinos autorizados por tarefa.')
        return response, task.move_choices

    def test_admin_can_move_to_every_other_status(self):
        response, choices = self.choices(self.admin)
        self.assertEqual(choices, [('criacao', 'Criação'), ('avaliacao', 'Avaliação'), ('concluido', 'Concluído')])
        self.assertContains(response, reverse('tarefa-transicoes', args=[self.mine.pk]))

    def test_responsible_only_gets_authorized_destination(self):
        _, choices = self.choices(self.owner)
        self.assertEqual(choices, [('criacao', 'Criação')])

    def test_responsible_in_evaluation_cannot_move(self):
        set_task_status(actor=self.admin, task_id=self.mine.pk, status='avaliacao', expected_version=1)
        _, choices = self.choices(self.owner)
        self.assertEqual(choices, [])

    def test_no_script_move_uses_existing_transition_and_preserves_task_fields(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('tarefas:board'))
        self.assertContains(response, 'data-task-move')
        self.assertContains(response, reverse('tarefas:transition', args=[self.mine.pk]))
        response = self.client.post(reverse('tarefas:transition', args=[self.mine.pk]),
                                    {'status': 'criacao', 'versao': 1})
        self.assertRedirects(response, reverse('tarefas:detail', args=[self.mine.pk]))
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, 'criacao')
        self.assertEqual(self.mine.versao, 2)
        self.assertIsNotNone(self.mine.inicio)
        self.assertIsNone(self.mine.conclusao)
        self.assertEqual(self.mine.descricao, 'Protótipo privado de Ana')
        self.assertEqual(list(self.mine.responsaveis.values_list('pk', flat=True)), [self.owner.pk])
        self.assertEqual(self.mine.prazo, self.service.prazo)
        self.assertEqual(self.mine.eventos.count(), 2)
