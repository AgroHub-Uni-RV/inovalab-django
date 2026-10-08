from django.test import TestCase

from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskModalTests(TaskFixtures, TestCase):
    headers = {'HTTP_X_TASK_MODAL': '1'}

    def setUp(self):
        self.client.force_login(self.admin)

    def test_create_and_update_get_return_only_modal_fragments(self):
        for path in ('/tarefas/nova/', f'/tarefas/{self.mine.pk}/editar/'):
            with self.subTest(path=path):
                response = self.client.get(path, **self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-task-modal-content')
                self.assertNotContains(response, '<html')
                self.assertNotContains(response, 'id="task-modal"')
                self.assertNotContains(response, 'id="sidebar"')
                self.assertIn('X-Task-Modal', response['Vary'])
                self.assertEqual(response['Cache-Control'], 'no-store')
                self.assertContains(response, f'action="{path}"')

    def test_modal_create_and_update_return_json_without_redirecting(self):
        create = self.client.post('/tarefas/nova/', self.form_payload(descricao='Criada no modal'),
                                  **self.headers)
        self.assertEqual(create.status_code, 201)
        self.assertNotIn('Location', create)
        task = Tarefa.objects.get(descricao='Criada no modal')
        self.assertEqual(create.json(), {
            'saved': True,
            'message': 'Tarefa criada com sucesso.',
            'detail_url': f'/tarefas/{task.pk}/',
        })

        update = self.client.post(f'/tarefas/{task.pk}/editar/', self.form_payload(
            descricao='Editada no modal', versao=1), **self.headers)
        self.assertEqual(update.status_code, 200)
        self.assertNotIn('Location', update)
        self.assertEqual(update.json(), {
            'saved': True,
            'message': 'Tarefa atualizada com sucesso.',
            'detail_url': f'/tarefas/{task.pk}/',
        })
        task.refresh_from_db()
        self.assertEqual((task.descricao, task.versao), ('Editada no modal', 2))

    def test_modal_validation_and_conflict_keep_the_form_fragment(self):
        invalid = self.client.post('/tarefas/nova/', self.form_payload(descricao='   '),
                                   **self.headers)
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'data-task-modal-content')
        self.assertContains(invalid, 'Confira os erros antes de salvar')
        self.assertFalse(Tarefa.objects.filter(descricao='').exists())

        conflict = self.client.post(f'/tarefas/{self.mine.pk}/editar/', self.form_payload(
            descricao='Versão antiga', versao=2), **self.headers)
        self.assertEqual(conflict.status_code, 409)
        self.assertContains(conflict, 'data-task-modal-content', status_code=409)
        self.assertContains(conflict, 'Versão antiga', status_code=409)

    def test_task_modal_is_available_once_to_admin_and_links_opt_in(self):
        for path in ('/tarefas/', '/painel/', f'/tarefas/{self.mine.pk}/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, 'id="task-modal"', count=1)
                self.assertContains(response, 'inovalab_app/tarefas/task-modal.js', count=1)
        self.assertContains(self.client.get('/tarefas/'), 'data-task-modal-trigger')
        self.assertContains(self.client.get('/painel/'), 'data-task-modal-trigger')
        self.assertContains(self.client.get(f'/tarefas/{self.mine.pk}/'), 'data-task-modal-trigger')

    def test_task_form_uses_searchable_checkbox_groups_and_sections(self):
        response = self.client.get('/tarefas/nova/')
        self.assertContains(response, 'data-task-choice-group="responsaveis"')
        self.assertContains(response, 'data-task-choice-group="equipamentos"')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'Pesquisar responsáveis')
        self.assertContains(response, 'Pesquisar equipamentos')
        for section in ('Serviço e prazo', 'Descrição da tarefa', 'Equipe e recursos'):
            self.assertContains(response, section)

        self.assertContains(response, 'aria-describedby="id_agendamento_servico_helptext"')
        self.assertContains(response, 'id="id_agendamento_servico_helptext"')

    def test_non_modal_posts_keep_the_existing_redirect_contract(self):
        response = self.client.post('/tarefas/nova/', self.form_payload(descricao='Fluxo sem JavaScript'))
        task = Tarefa.objects.get(descricao='Fluxo sem JavaScript')
        self.assertRedirects(response, f'/tarefas/{task.pk}/', fetch_redirect_response=False)
