from django.test import TestCase

from inovalab_app.catalogo.models import Equipamento
from inovalab_app.catalogo.services import delete_equipment, restore_default_equipment
from inovalab_app.tarefas.services import save_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class EquipmentDeletionLinksTests(TaskFixtures, TestCase):
    def test_excluding_and_restoring_default_preserves_task_links_and_history(self):
        equipment = Equipamento.objects.get(codigo_inicial='impressora-3d')
        task = save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1, data={'equipamentos': [equipment]})
        before = list(task.eventos.values())
        delete_equipment(actor=self.admin, equipment_id=equipment.pk)
        task.refresh_from_db()
        self.assertEqual(task.equipamento_id, equipment.pk)
        self.assertEqual(list(task.equipamentos.values_list('pk', flat=True)), [equipment.pk])
        self.assertEqual(list(task.eventos.values()), before)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(f'/tarefas/{task.pk}/'), equipment.nome)
        restore_default_equipment(actor=self.admin)
        task.refresh_from_db()
        self.assertEqual(list(task.equipamentos.values_list('pk', flat=True)), [equipment.pk])
        self.assertEqual(list(task.eventos.values()), before)

    def test_editing_exposes_delete_only_to_administrator(self):
        equipment = Equipamento.objects.first()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(f'/catalogo/equipamentos/{equipment.pk}/editar/'), 'Excluir equipamento')
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(f'/catalogo/equipamentos/{equipment.pk}/'), 'Excluir equipamento')
