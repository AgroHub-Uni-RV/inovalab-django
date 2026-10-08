from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from inovalab_app.catalogo.models import Equipamento
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.selectors import visible_tasks
from inovalab_app.tarefas.services import TaskConflict, allowed_actions, save_task, set_task_status
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class MultipleLinksFixtures(TaskFixtures):
    def setUp(self):
        self.equipment = list(Equipamento.objects.order_by('pk')[:2])
        self.materials = [Material.objects.create(nome=name, categoria='Filamento', quantidade=100,
                                                 unidade='g', fonte='Lab') for name in ('PLA plural', 'ABS plural')]

    def create_multiple(self, **overrides):
        return save_task(actor=self.admin, data={
            'agendamento_servico': self.booking, 'descricao': 'Tarefa da equipe',
            'responsaveis': [self.owner, self.other], 'equipamentos': self.equipment,
            'materiais_gastos': [{'material': self.materials[0], 'quantidade': '20 g'},
                                {'material': self.materials[1], 'quantidade': 'meia bobina'}],
            **overrides,
        })


class MultipleTaskLinksTests(MultipleLinksFixtures, TestCase):
    def test_multiple_links_quantities_history_and_stock(self):
        task = self.create_multiple()
        self.assertEqual(set(task.responsaveis.all()), {self.owner, self.other})
        self.assertEqual(set(task.equipamentos.all()), set(self.equipment))
        self.assertEqual(list(task.materiais_gastos.order_by('material_id').values_list('material_id', 'quantidade')),
                         [(self.materials[0].pk, '20 g'), (self.materials[1].pk, 'meia bobina')])
        self.assertEqual(task.prazo, self.service.prazo)
        self.assertEqual(task.eventos.get().alteracoes['responsaveis']['novo'], [self.owner.pk, self.other.pk])
        for material in self.materials:
            material.refresh_from_db()
            self.assertEqual(material.quantidade, 100)

    def test_every_responsible_can_access_and_execute_shared_task(self):
        task = self.create_multiple()
        for actor in (self.owner, self.other):
            self.assertEqual(visible_tasks(actor).filter(pk=task.pk).count(), 1)
            self.assertEqual(allowed_actions(actor, task), ['iniciar'])
        task = set_task_status(actor=self.other, task_id=task.pk, status='criacao', expected_version=1)
        task = set_task_status(actor=self.owner, task_id=task.pk, status='avaliacao', expected_version=2)
        self.assertEqual((task.status, task.versao), ('avaliacao', 3))
        self.assertEqual(allowed_actions(self.other, task), [])

    def test_removing_responsible_revokes_access_and_records_list_changes(self):
        task = self.create_multiple()
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=1,
                         data={'responsaveis': [self.other]})
        self.assertFalse(visible_tasks(self.owner).filter(pk=task.pk).exists())
        self.assertTrue(visible_tasks(self.other).filter(pk=task.pk).exists())
        self.assertEqual(task.eventos.first().alteracoes['responsaveis'],
                         {'anterior': [self.owner.pk, self.other.pk], 'novo': [self.other.pk]})

    def test_invalid_or_duplicate_lists_and_quantities_are_rejected_atomically(self):
        invalid = [
            {'responsaveis': []}, {'responsaveis': [self.owner, self.owner]},
            {'responsaveis': [self.owner.pk]}, {'equipamentos': [self.equipment[0], self.equipment[0]]},
            {'materiais_gastos': [{'material': self.materials[0], 'quantidade': '1'},
                                  {'material': self.materials[0], 'quantidade': '2'}]},
            {'materiais_gastos': [{'material': None, 'quantidade': '1 g'}]},
            {'materiais_gastos': [{'material': self.materials[0], 'quantidade': 'x' * 151}]},
            {'responsaveis': [self.owner], 'responsavel': self.other},
        ]
        initial = visible_tasks(self.admin).count()
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.create_multiple(**payload)
        self.assertEqual(visible_tasks(self.admin).count(), initial)

    def test_existing_unavailable_references_retained_new_ones_rejected(self):
        task = self.create_multiple()
        self.other.is_active = False
        self.other.save(update_fields=['is_active'])
        self.equipment[1].excluido_em = timezone.now()
        self.equipment[1].save(update_fields=['excluido_em'])
        self.materials[1].status = 'indisponivel'
        self.materials[1].save(update_fields=['status'])
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'descricao': 'Preservar'})
        self.assertEqual(task.responsaveis.count(), 2)
        self.assertEqual(task.equipamentos.count(), 2)
        self.assertEqual(task.materiais_gastos.count(), 2)
        with self.assertRaises(ValidationError):
            self.create_multiple()

    def test_stale_or_invalid_edit_leaves_every_link_and_event_unchanged(self):
        task = self.create_multiple()
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'descricao': 'Versão nova'})
        with self.assertRaises(TaskConflict):
            save_task(actor=self.admin, task_id=task.pk, expected_version=1,
                      data={'responsaveis': [self.owner], 'equipamentos': [], 'materiais_gastos': []})
        with self.assertRaises(ValidationError):
            save_task(actor=self.admin, task_id=task.pk, expected_version=2,
                      data={'responsaveis': [], 'equipamentos': [], 'materiais_gastos': []})
        self.assertEqual((task.responsaveis.count(), task.equipamentos.count(), task.materiais_gastos.count()), (2, 2, 2))
        self.assertEqual(task.eventos.count(), 2)

    def test_secondary_references_are_protected_from_physical_deletion(self):
        self.create_multiple()
        for resource in (self.other, self.equipment[1], self.materials[1]):
            with self.subTest(resource=resource), self.assertRaises(ProtectedError):
                resource.delete()

    def test_singleton_compatibility_populates_plural_relations(self):
        self.assertEqual(list(self.mine.responsaveis.all()), [self.owner])
        task = save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1,
                         data={'equipamento': self.equipment[0], 'material_gasto': self.materials[0],
                               'quantidade_material_gasto': '20 g'})
        self.assertEqual(list(task.equipamentos.all()), [self.equipment[0]])
        self.assertEqual(task.materiais_gastos.get().quantidade, '20 g')

    def test_history_failure_rolls_back_changes_to_task_and_all_associations(self):
        task = self.create_multiple()
        with patch('inovalab_app.tarefas.services.EventoTarefa.objects.create', side_effect=RuntimeError('Failure after writes')):
            with self.assertRaises(RuntimeError):
                save_task(actor=self.admin, task_id=task.pk, expected_version=1,
                          data={'descricao': 'Não gravar', 'responsaveis': [self.other],
                                'equipamentos': [], 'materiais_gastos': []})
        task.refresh_from_db()
        self.assertEqual((task.descricao, task.versao, task.eventos.count()), ('Tarefa da equipe', 1, 1))
        self.assertEqual((task.responsaveis.count(), task.equipamentos.count(), task.materiais_gastos.count()), (2, 2, 2))

    def test_removed_owner_is_blocked_by_every_web_and_api_endpoint(self):
        task = self.create_multiple()
        save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'responsaveis': [self.other]})
        self.client.force_login(self.owner)
        for prefix in ('/tarefas/', '/api/v1/tarefas/'):
            url = f'{prefix}{task.pk}/'
            for response in (self.client.get(url), self.client.get(url+'historico/'),
                             self.client.post(url+'transicoes/', {'status': 'criacao', 'versao': 2})):
                self.assertEqual(response.status_code, 404)

    def test_singular_edit_cannot_discard_secondary_links_unknown_to_old_client(self):
        for payload in ({'responsavel': self.owner}, {'equipamento': self.equipment[0]},
                        {'material_gasto': self.materials[0]}, {'quantidade_material_gasto': '10 g'}):
            with self.subTest(payload=payload):
                task = self.create_multiple()
                with self.assertRaises(ValidationError):
                    save_task(actor=self.admin, task_id=task.pk, expected_version=1, data=payload)
                task.refresh_from_db()
                self.assertEqual((task.versao, task.eventos.count()), (1, 1))
                self.assertEqual((task.responsaveis.count(), task.equipamentos.count(), task.materiais_gastos.count()), (2, 2, 2))
