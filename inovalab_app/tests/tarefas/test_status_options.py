from django.test import TestCase
from django.core.exceptions import ValidationError
from inovalab_app.tarefas.models import StatusTarefa
from inovalab_app.tarefas.services import TaskConflict, save_task, set_task_status, transition_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskStatusOptionsTests(TaskFixtures, TestCase):
    def test_admin_select_includes_every_status(self):
        self.client.force_login(self.admin)
        response = self.client.get(f'/tarefas/{self.mine.pk}/')
        self.assertEqual(list(response.context['status_form'].fields['status'].choices), StatusTarefa.choices)
        for value in StatusTarefa.values:
            self.assertNotContains(response, f'value="{value}" disabled')

    def test_admin_can_move_directly_between_all_statuses_with_history_and_dates(self):
        for source in StatusTarefa.values:
            for destination in StatusTarefa.values:
                with self.subTest(source=source, destination=destination):
                    task = save_task(actor=self.admin, data={
                        'agendamento_servico': self.booking, 'responsavel': self.owner,
                        'descricao': 'Mudança administrativa direta',
                    })
                    task = set_task_status(actor=self.admin, task_id=task.pk, status=source, expected_version=1)
                    version, events, started = task.versao, task.eventos.count(), task.inicio
                    task = set_task_status(actor=self.admin, task_id=task.pk, status=destination, expected_version=version)
                    task.refresh_from_db()
                    self.assertEqual(task.status, destination)
                    changed = source != destination
                    self.assertEqual((task.versao, task.eventos.count()), (version + changed, events + changed))
                    if destination != 'demanda':
                        self.assertIsNotNone(task.inicio)
                    if started:
                        self.assertEqual(task.inicio, started)
                    self.assertEqual(task.conclusao is not None, destination == 'concluido')
                    if changed:
                        event = task.eventos.first()
                        self.assertEqual((event.status_anterior, event.status_novo, event.ator_id),
                                         (source, destination, self.admin.pk))

    def test_admin_direct_web_and_api_changes_preserve_version_protection(self):
        self.client.force_login(self.admin)
        response = self.client.post(f'/tarefas/{self.mine.pk}/transicoes/', {'status': 'concluido', 'versao': 1})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), 'Alterou o status')
        response = self.client.post(f'/api/v1/tarefas/{self.mine.pk}/transicoes/',
                                    {'status': 'demanda', 'versao': 2}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/api/v1/tarefas/{self.mine.pk}/transicoes/',
                                    {'status': 'concluido', 'versao': 2}, content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.status, self.mine.versao, self.mine.eventos.count()), ('demanda', 3, 3))

    def test_invalid_status_and_stale_admin_request_do_not_change_task(self):
        with self.assertRaises(ValidationError):
            set_task_status(actor=self.admin, task_id=self.mine.pk, status='inexistente', expected_version=1)
        with self.assertRaises(TaskConflict):
            set_task_status(actor=self.admin, task_id=self.mine.pk, status='concluido', expected_version=2)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.status, self.mine.versao, self.mine.eventos.count()), ('demanda', 1, 1))

    def test_owner_sees_every_status_even_while_waiting_for_admin_approval(self):
        task = transition_task(actor=self.owner, task_id=self.mine.pk, action='iniciar', expected_version=1)
        task = transition_task(actor=self.owner, task_id=task.pk, action='enviar', expected_version=2)
        self.client.force_login(self.owner)
        response = self.client.get(f'/tarefas/{task.pk}/')
        self.assertContains(response, 'name="status"')
        self.assertEqual(list(response.context['status_form'].fields['status'].choices), StatusTarefa.choices)
        self.assertContains(response, 'value="concluido" disabled')
        self.assertContains(response, 'Salvar status')
        task.refresh_from_db()
        self.assertEqual((task.status, task.versao), ('avaliacao', 3))

    def test_showing_every_status_does_not_enable_forbidden_transition(self):
        self.client.force_login(self.owner)
        response = self.client.post(f'/tarefas/{self.mine.pk}/transicoes/', {'status':'concluido', 'versao':1})
        self.assertEqual(response.status_code, 400)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.status, self.mine.versao, self.mine.eventos.count()), ('demanda', 1, 1))
