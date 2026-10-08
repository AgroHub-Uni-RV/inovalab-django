from unittest.mock import patch

from django.test import Client, TestCase

from inovalab_app.tarefas.services import TaskConflict, save_task

from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskModalTests(TaskFixtures, TestCase):
    headers = {'HTTP_X_TASK_MODAL': '1'}

    def setUp(self):
        self.client.force_login(self.admin)

    def test_create_update_and_detail_get_return_only_modal_fragments(self):
        for path in ('/tarefas/nova/', f'/tarefas/{self.mine.pk}/editar/', f'/tarefas/{self.mine.pk}/'):
            with self.subTest(path=path):
                response = self.client.get(path, **self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-task-modal-content')
                self.assertNotContains(response, '<html')
                self.assertNotContains(response, 'id="task-modal"')
                self.assertNotContains(response, 'id="sidebar"')
                self.assertIn('X-Task-Modal', response['Vary'])
                self.assertEqual(response['Cache-Control'], 'no-store')
                expected_action = f'{path}transicoes/' if path == f'/tarefas/{self.mine.pk}/' else path
                self.assertContains(response, f'action="{expected_action}"')

    def test_modal_create_returns_json_and_update_returns_refreshed_detail(self):
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
        self.assertContains(update, 'data-task-modal-content')
        self.assertContains(update, 'data-task-detail')
        self.assertContains(update, 'Editada no modal')
        self.assertContains(update, 'Tarefa atualizada com sucesso.')
        task.refresh_from_db()
        self.assertEqual((task.descricao, task.versao), ('Editada no modal', 2))

    def test_modal_transition_returns_updated_detail_and_conflict_in_place(self):
        self.client.force_login(self.owner)
        path = f'/tarefas/{self.mine.pk}/transicoes/'
        updated = self.client.post(path, {'status': 'criacao', 'versao': 1}, **self.headers)
        self.assertEqual(updated.status_code, 200)
        self.assertContains(updated, 'data-task-detail')
        self.assertContains(updated, 'Tarefa atualizada com sucesso.')
        self.assertContains(updated, 'value="2"')

        conflict = self.client.post(path, {'status': 'avaliacao', 'versao': 1}, **self.headers)
        self.assertEqual(conflict.status_code, 409)
        self.assertContains(conflict, 'data-task-detail', status_code=409)
        self.assertContains(conflict, 'alterada', status_code=409)

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

        self.client.force_login(self.owner)
        for path in ('/tarefas/', '/painel/'):
            with self.subTest(owner_path=path):
                response = self.client.get(path)
                self.assertContains(response, 'id="task-modal"', count=1)
                self.assertContains(response, 'data-task-detail-trigger')

    def test_task_detail_uses_standardized_summary_resources_and_history(self):
        response = self.client.get(f'/tarefas/{self.mine.pk}/')
        self.assertContains(response, 'data-task-detail')
        self.assertContains(response, 'task-detail-summary')
        self.assertContains(response, 'task-resource-section', count=3)
        self.assertContains(response, 'task-history-timeline')

    def test_edit_cancel_can_return_to_detail_without_leaving_modal(self):
        response = self.client.get(f'/tarefas/{self.mine.pk}/editar/', **self.headers)
        self.assertContains(response, f'data-task-detail-trigger href="/tarefas/{self.mine.pk}/"')

    def test_transition_validation_is_shown_as_error_without_changes(self):
        response = self.client.post(f'/tarefas/{self.mine.pk}/transicoes/',
                                    {'status': 'invalid', 'versao': 1}, **self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'role="alert"', status_code=400)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.status, self.mine.versao, self.mine.eventos.count()), ('demanda', 1, 1))

    def test_conflict_does_not_disclose_task_after_access_revoked_during_post(self):
        self.client.force_login(self.owner)

        def reassign_before_transition(**kwargs):
            save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1,
                      data={'responsaveis': [self.other]})
            raise TaskConflict('A tarefa foi alterada em outra tela.')

        with patch('inovalab_app.tarefas.views.set_task_status', side_effect=reassign_before_transition):
            response = self.client.post(f'/tarefas/{self.mine.pk}/transicoes/',
                                        {'status': 'criacao', 'versao': 1}, **self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, self.mine.descricao, status_code=404)

    def test_detail_fragment_preserves_scope_and_status_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.get(f'/tarefas/{self.theirs.pk}/', **self.headers).status_code, 404)
        client.get(f'/tarefas/{self.mine.pk}/', **self.headers)
        path = f'/tarefas/{self.mine.pk}/transicoes/'
        self.assertEqual(client.post(path, {'status': 'criacao', 'versao': 1}, **self.headers).status_code, 403)
        response = client.post(path, {'status': 'criacao', 'versao': 1},
                               HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value, **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-task-detail')

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
