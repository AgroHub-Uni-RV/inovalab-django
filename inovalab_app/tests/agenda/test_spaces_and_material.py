from django.core.exceptions import ValidationError
from django.test import TestCase
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.forms import TaskForm
from inovalab_app.tarefas.services import save_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskMaterialTests(TaskFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(nome='PLA azul', categoria='Filamento', quantidade=500,
                                               unidade='g', fonte='Laboratório')
        cls.other_material = Material.objects.create(nome='ABS', categoria='Filamento', quantidade=200,
                                                     unidade='kg', fonte='Lab', status='indisponivel')

    def create(self, **fields):
        return save_task(actor=self.admin, data={'agendamento_servico': self.booking,
            'responsavel': self.owner, 'descricao': 'Protótipo', **fields})

    def test_material_is_optional_and_quantity_belongs_to_selected_material(self):
        for fields in ({}, {'material_gasto': self.material},
                       {'material_gasto': self.material, 'quantidade_material_gasto': '12,125 g'}):
            task = self.create(**fields)
            self.assertEqual(task.quantidade_material_gasto, fields.get('quantidade_material_gasto', ''))
        with self.assertRaises(ValidationError):
            self.create(quantidade_material_gasto='Meia bobina')
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantidade, 500)

    def test_unavailable_material_cannot_be_added_to_new_task(self):
        with self.assertRaises(ValidationError):
            self.create(material_gasto=self.other_material)

    def test_retained_unavailable_material_allows_edit_without_inventory_change(self):
        task = self.create(material_gasto=self.material, quantidade_material_gasto='12 g')
        Material.objects.filter(pk=self.material.pk).update(status='indisponivel')
        form = TaskForm(instance=task)
        material_field = form.material_formset.forms[0].fields['material']
        self.assertIn(self.material, material_field.queryset)
        self.assertNotIn(self.other_material, material_field.queryset)
        changed = save_task(actor=self.admin, task_id=task.pk, expected_version=1,
                            data={'descricao': 'Corrigido'})
        self.assertEqual(changed.material_gasto_id, self.material.pk)
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantidade, 500)

    def test_removing_material_records_previous_value_in_task_history(self):
        task = self.create(material_gasto=self.material, quantidade_material_gasto='12 g')
        changed = save_task(actor=self.admin, task_id=task.pk, expected_version=1,
                            data={'material_gasto': None, 'quantidade_material_gasto': ''})
        event = changed.eventos.get(acao='editar')
        self.assertEqual(event.alteracoes['material_gasto'], {'anterior': self.material.pk, 'novo': None})
        self.assertEqual(event.alteracoes['quantidade_material_gasto'], {'anterior': '12 g', 'novo': ''})
