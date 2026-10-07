from datetime import datetime
import re

from django.test import Client, TestCase

from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.services import delete_task, save_task, transition_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskWebTests(TaskFixtures, TestCase):
    def test_anonymous_redirects_to_login(self):
        for path in ('/tarefas/', '/tarefas/nova/', f'/tarefas/{self.mine.pk}/'):
            self.assertRedirects(self.client.get(path), f'/entrar/?next={path}', fetch_redirect_response=False)

    def test_owner_board_counts_and_detail_only_include_own_tasks(self):
        self.client.force_login(self.owner)
        response = self.client.get('/tarefas/')
        self.assertContains(response, self.mine.descricao)
        self.assertNotContains(response, self.theirs.descricao)
        self.assertNotContains(response, '/tarefas/nova/')
        columns = response.context['columns']
        self.assertEqual([column['count'] for column in columns], [1, 0, 0, 0])
        self.assertContains(self.client.get(f'/tarefas/{self.mine.pk}/'), 'Iniciar execução')

    def test_foreign_detail_history_and_transition_are_404(self):
        self.client.force_login(self.owner)
        path = f'/tarefas/{self.theirs.pk}/'
        for response in (self.client.get(path), self.client.get(path + 'historico/'),
                         self.client.post(path + 'transicoes/', {'acao': 'iniciar', 'versao': 1})):
            self.assertEqual(response.status_code, 404)

    def test_admin_creates_edits_reassigns_and_deletes_with_confirmation(self):
        self.client.force_login(self.admin)
        response = self.client.post('/tarefas/nova/', self.payload(), follow=False)
        task = Tarefa.objects.get(descricao='Nova tarefa')
        self.assertRedirects(response, f'/tarefas/{task.pk}/', fetch_redirect_response=False)
        response = self.client.post(f'/tarefas/{task.pk}/editar/', self.payload(descricao='Reatribuída', responsavel=self.other.pk, versao=1))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual((task.responsavel_id, task.versao), (self.other.pk, 2))
        self.assertContains(self.client.get(f'/tarefas/{task.pk}/excluir/'), 'Confirmar exclusão')
        self.assertIsNone(task.excluida_em)
        self.assertRedirects(self.client.post(f'/tarefas/{task.pk}/excluir/', {'versao': 2}), '/tarefas/', fetch_redirect_response=False)
        self.assertEqual(self.client.get(f'/tarefas/{task.pk}/').status_code, 404)

    def test_regular_user_and_staff_cannot_manage_own_task(self):
        for actor, task in ((self.owner, self.mine), (self.other, self.theirs)):
            self.client.force_login(actor)
            for path in ('/tarefas/nova/', f'/tarefas/{task.pk}/editar/', f'/tarefas/{task.pk}/excluir/'):
                self.assertEqual(self.client.get(path).status_code, 403)
                self.assertEqual(self.client.post(path, self.payload(versao=1)).status_code, 403)

    def test_owner_can_start_and_submit_but_not_approve(self):
        self.client.force_login(self.owner)
        path = f'/tarefas/{self.mine.pk}/transicoes/'
        for action, version in (('iniciar', 1), ('enviar', 2)):
            self.assertRedirects(self.client.post(path, {'acao': action, 'versao': version}), f'/tarefas/{self.mine.pk}/', fetch_redirect_response=False)
        detail = self.client.get(f'/tarefas/{self.mine.pk}/')
        self.assertNotContains(detail, 'Aprovar entrega')
        self.assertEqual(self.client.post(path, {'acao': 'aprovar', 'versao': 3}).status_code, 403)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, 'avaliacao')

    def test_posting_metadata_with_transition_is_rejected_without_partial_change(self):
        self.client.force_login(self.owner)
        response = self.client.post(f'/tarefas/{self.mine.pk}/transicoes/',
                                    {'acao': 'iniciar', 'versao': 1, 'responsavel': self.other.pk})
        self.assertEqual(response.status_code, 400)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.status, self.mine.versao), ('demanda', 1))

    def test_protected_fields_submitted_in_admin_form_are_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(f'/tarefas/{self.mine.pk}/editar/', self.payload(versao=1, status='concluido'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.status, self.mine.versao), ('demanda', 1))

    def test_stale_edit_and_transition_render_409_without_changes(self):
        save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1, data={'descricao': 'Nova versão'})
        self.client.force_login(self.admin)
        response = self.client.post(f'/tarefas/{self.mine.pk}/editar/', self.payload(descricao='Antiga', versao=1))
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'alterada', status_code=409)
        response = self.client.post(f'/tarefas/{self.mine.pk}/transicoes/', {'acao': 'iniciar', 'versao': 1})
        self.assertEqual(response.status_code, 409)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.descricao, self.mine.versao), ('Nova versão', 2))

    def test_history_reassignment_and_soft_delete_follow_same_scope(self):
        task = transition_task(actor=self.owner, task_id=self.mine.pk, action='iniciar', expected_version=1)
        self.client.force_login(self.owner)
        response = self.client.get(f'/tarefas/{task.pk}/historico/')
        self.assertContains(response, 'ana')
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=2, data={'responsavel': self.other})
        self.assertEqual(self.client.get(f'/tarefas/{task.pk}/historico/').status_code, 404)
        self.assertEqual([c['count'] for c in self.client.get('/tarefas/').context['columns']], [0, 0, 0, 0])
        delete_task(actor=self.admin, task_id=task.pk, expected_version=3)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f'/tarefas/{task.pk}/historico/').status_code, 404)

    def test_csrf_required_and_transition_endpoint_is_post_only(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        path = f'/tarefas/{self.mine.pk}/transicoes/'
        self.assertEqual(client.post(path, {'acao': 'iniciar', 'versao': 1}).status_code, 403)
        self.assertEqual(client.get(path).status_code, 405)
        client.get(f'/tarefas/{self.mine.pk}/')
        self.assertEqual(client.post(path, {'acao': 'iniciar', 'versao': 1}, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 302)

    def test_create_form_errors_keep_input_and_existing_inactive_refs_remain_editable(self):
        self.client.force_login(self.admin)
        response = self.client.post('/tarefas/nova/', self.payload(descricao='   '))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.owner.is_active = False
        self.owner.save()
        self.service.status = 'indisponivel'
        self.service.save()
        response = self.client.post(f'/tarefas/{self.mine.pk}/editar/', self.payload(descricao='Mantida', versao=1))
        self.assertEqual(response.status_code, 302)

    def test_home_has_task_navigation(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get('/perfil/'), '/tarefas/')

    def test_editing_description_preserves_existing_deadline_precision(self):
        deadline = datetime.fromisoformat('2026-11-01T14:22:59.123456-03:00')
        task = save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1, data={'prazo': deadline})
        self.client.force_login(self.admin)
        path = f'/tarefas/{task.pk}/editar/'
        html = self.client.get(path).content.decode()
        rendered_deadline = re.search(r'name="prazo"[^>]*value="([^"]+)"', html).group(1)
        self.assertEqual(rendered_deadline, '2026-11-01T14:22')
        response = self.client.post(path, self.payload(descricao='Somente descrição', prazo=rendered_deadline, versao=2))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.prazo, deadline)
        self.assertEqual(task.descricao, 'Somente descrição')
        response = self.client.post(path, self.payload(descricao='Somente descrição',
                                                      prazo='2026-11-01T14:23', versao=3))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual((task.prazo.minute, task.prazo.second, task.prazo.microsecond), (23, 0, 0))
