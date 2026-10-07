from django.test import TestCase

from inovalab_app.catalogo.models import Servico
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.services import save_task, transition_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskFrontendTests(TaskFixtures, TestCase):
    def test_search_and_status_filters_do_not_expose_foreign_tasks(self):
        self.client.force_login(self.owner)
        response = self.client.get('/tarefas/', {'q': self.theirs.descricao})
        self.assertEqual(response.context['paginator'].count, 0)
        self.assertEqual(sum(response.context['stat_counts'].values()), 0)
        response = self.client.get('/tarefas/', {'status': 'criacao'})
        self.assertEqual(response.context['paginator'].count, 0)
        self.assertEqual(response.context['stat_counts']['demanda'], 1)

    def test_service_filter_and_invalid_choices_are_safe(self):
        service = Servico.objects.create(nome='Outro serviço')
        task = save_task(actor=self.admin, data={'servico': service, 'responsavel': self.owner, 'descricao': 'Buscável'})
        self.client.force_login(self.admin)
        response = self.client.get('/tarefas/', {'servico': str(service.pk), 'q': 'Buscável'})
        self.assertEqual([item.pk for item in response.context['object_list']], [task.pk])
        for value in ('²', 'abc', '9'*50):
            response = self.client.get('/tarefas/', {'servico': value, 'status': 'naoexiste'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['selected_status'], '')

    def test_pagination_preserves_filters_and_detail_history_is_real(self):
        Tarefa.objects.bulk_create([Tarefa(servico=self.service, responsavel=self.owner, descricao='Busca teste') for _ in range(26)])
        self.client.force_login(self.owner)
        response = self.client.get('/tarefas/', {'q': 'Busca teste', 'status': 'demanda'})
        self.assertEqual(len(response.context['object_list']), 25)
        self.assertContains(response, 'q=Busca+teste')
        self.assertContains(response, 'status=demanda')
        detail = self.client.get(f'/tarefas/{self.mine.pk}/')
        self.assertContains(detail, 'sheet-sidebar')
        self.assertContains(detail, 'Histórico')
