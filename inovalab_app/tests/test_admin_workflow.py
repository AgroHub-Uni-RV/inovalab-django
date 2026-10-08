from django.contrib.admin import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.services import save_task
from inovalab_app.tests.agenda.helpers import make_booking


class AdminWorkflowTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser('admin-fluxo')
        self.request = RequestFactory().get('/admin/')
        self.request.user = self.actor

    def test_task_admin_cannot_bypass_domain_creation_editing_or_deletion(self):
        admin = site._registry[Tarefa]
        self.assertFalse(admin.has_add_permission(self.request))
        self.assertFalse(admin.has_change_permission(self.request))
        self.assertFalse(admin.has_delete_permission(self.request))
        self.assertTrue(admin.has_view_permission(self.request))

    def test_equipment_soft_delete_confirmation_keeps_protected_task_and_row(self):
        equipment = Equipamento.objects.first()
        task = save_task(actor=self.actor, data={'agendamento_servico': make_booking(actor=self.actor),
            'responsavel': self.actor, 'descricao': 'Preservar vínculo', 'equipamento': equipment})
        admin = site._registry[Equipamento]
        _, _, permissions, protected = admin.get_deleted_objects([equipment], self.request)
        self.assertFalse(protected)
        self.assertFalse(permissions)
        self.client.force_login(self.actor)
        url = f'/admin/inovalab_app/equipamento/{equipment.pk}/delete/'
        response = self.client.post(url, {'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        equipment.refresh_from_db()
        task.refresh_from_db()
        self.assertIsNotNone(equipment.excluido_em)
        self.assertEqual(task.equipamento_id, equipment.pk)
