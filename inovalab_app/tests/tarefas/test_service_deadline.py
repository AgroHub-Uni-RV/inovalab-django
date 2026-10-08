from datetime import datetime, timezone
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from inovalab_app.agenda.services import save_booking
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.services import save_task
from inovalab_app.tests.agenda.helpers import make_booking
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskServiceDeadlineTests(TaskFixtures, TestCase):
    def test_new_task_inherits_service_deadline(self):
        self.assertEqual(self.mine.prazo, self.booking.servico.prazo)

    def test_changing_service_deadline_updates_existing_task_without_task_edit(self):
        deadline = datetime(2099, 12, 3, 17, 22, 37, 123456, tzinfo=timezone.utc)
        save_booking(actor=self.admin, category='servico', booking_id=self.booking.pk,
                     expected_version=1, data={'prazo': deadline})
        task = Tarefa.objects.get(pk=self.mine.pk)
        self.assertEqual(task.prazo, deadline)
        self.assertEqual((task.versao, task.eventos.count()), (1, 1))

    def test_reassigning_booking_uses_new_service_deadline(self):
        booking = make_booking(actor=self.admin, prazo=datetime(2099, 12, 4, 18, tzinfo=timezone.utc))
        task = save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1,
                         data={'agendamento_servico': booking})
        self.assertEqual(task.prazo, booking.servico.prazo)

    def test_task_deadline_cannot_be_set_independently_in_domain(self):
        with self.assertRaises(ValidationError):
            save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1,
                      data={'prazo': datetime(2099, 12, 1, 18, tzinfo=timezone.utc)})
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.versao, 1)

    def test_api_deadline_is_service_value_and_read_only(self):
        api = APIClient()
        api.force_login(self.admin)
        url = f'/api/v1/tarefas/{self.mine.pk}/'
        self.assertEqual(datetime.fromisoformat(api.get(url).data['prazo']), self.booking.servico.prazo)
        self.assertEqual(api.patch(url, {'versao': 1, 'prazo': '2099-12-04T17:00:00-03:00'}, format='json').status_code, 400)
        self.assertEqual(api.post('/api/v1/tarefas/', self.payload(prazo='2099-12-04T17:00:00-03:00'), format='json').status_code, 400)

    def test_form_shows_linked_deadline_without_editable_task_deadline(self):
        self.client.force_login(self.admin)
        response = self.client.get(f'/tarefas/{self.mine.pk}/editar/')
        self.assertNotIn('prazo', response.context['form'].fields)
        self.assertContains(response, 'Prazo do serviço')
        self.assertContains(response, '01/11/2099 15:00')
        self.assertNotContains(response, 'name="prazo"')

    def test_old_stored_deadline_remains_legacy_without_overriding_service(self):
        old = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
        Tarefa.objects.filter(pk=self.mine.pk).update(prazo_legado=old)
        task = Tarefa.objects.get(pk=self.mine.pk)
        self.assertEqual(task.prazo_legado, old)
        self.assertEqual(task.prazo, self.booking.servico.prazo)
