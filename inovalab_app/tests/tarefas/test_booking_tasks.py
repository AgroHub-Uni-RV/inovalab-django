from datetime import datetime, timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.forms import TaskForm
from inovalab_app.agenda.services import cancel_booking
from inovalab_app.tests.agenda.helpers import make_booking, make_service
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.services import save_task


class BookingTaskTests(TestCase):
    def test_database_rejects_missing_booking_and_responsible(self):
        for fields in ({'responsavel': self.owner}, {'agendamento_servico': self.booking}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                Tarefa.objects.create(descricao='Vínculos obrigatórios', **fields)

    def test_deleted_equipment_is_retained_but_unavailable_for_new_assignments(self):
        from inovalab_app.catalogo.services import delete_equipment
        equipment = Equipamento.objects.first()
        task = save_task(actor=self.admin, data={'agendamento_servico': self.booking,
            'responsavel': self.owner, 'descricao': 'Original', 'equipamento': equipment})
        delete_equipment(actor=self.admin, equipment_id=equipment.pk)
        delete_equipment(actor=self.admin, equipment_id=equipment.pk)
        self.assertIn(equipment, TaskForm(instance=task).fields['equipamentos'].queryset)
        self.assertNotIn(equipment, TaskForm().fields['equipamentos'].queryset)
        saved = save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'descricao': 'Retido'})
        self.assertEqual(saved.equipamento_id, equipment.pk)
        with self.assertRaises(ValidationError):
            save_task(actor=self.admin, data={'agendamento_servico': self.booking,
                'responsavel': self.owner, 'descricao': 'Outro', 'equipamento': equipment})

    def test_status_api_preserves_permissions_versions_and_noop_history(self):
        task = save_task(actor=self.admin, data={'agendamento_servico': self.booking,
            'responsavel': self.owner, 'descricao': 'Mudança por status'})
        api = APIClient()
        api.force_login(self.owner)
        url = f'/api/v1/tarefas/{task.pk}/transicoes/'
        response = api.post(url, {'status': 'demanda', 'versao': 1}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        task.refresh_from_db()
        self.assertEqual((task.versao, task.eventos.count()), (1, 1))
        self.assertEqual(api.post(url, {'status': 'concluido', 'versao': 1}, format='json').status_code, 400)
        self.assertEqual(api.post(url, {'status': 'criacao', 'acao': 'iniciar', 'versao': 1}, format='json').status_code, 400)
        self.assertEqual(api.post(url, {'status': 'criacao', 'versao': 1}, format='json').status_code, 200)
        self.assertEqual(api.post(url, {'status': 'avaliacao', 'versao': 1}, format='json').status_code, 409)
        self.assertEqual(api.post(url, {'status': 'avaliacao', 'versao': 2}, format='json').status_code, 200)
        self.assertEqual(api.post(url, {'status': 'concluido', 'versao': 3}, format='json').status_code, 403)
        api.force_login(self.admin)
        self.assertEqual(api.post(url, {'status': 'concluido', 'versao': 3}, format='json').status_code, 200)
        task.refresh_from_db()
        self.assertIsNotNone(task.inicio)
        self.assertIsNotNone(task.conclusao)
        self.assertEqual((task.versao, task.eventos.count()), (4, 4))

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('tarefas-gestor')
        cls.owner = get_user_model().objects.create_user('tarefas-dono', is_staff=True)
        cls.booking = make_booking(service=make_service(titulo='Projeto', descricao='Descrição',
            prazo=datetime(2099, 1, 1, 17, tzinfo=timezone.utc)), actor=cls.admin)

    def test_task_requires_booking_and_responsible(self):
        with self.assertRaises(ValidationError):
            save_task(actor=self.admin, data={'descricao': 'Sem vínculo', 'responsavel': self.owner})
        with self.assertRaises(ValidationError):
            save_task(actor=self.admin, data={'descricao': 'Sem responsável', 'agendamento_servico': self.booking})

    def test_optional_resources_and_text_quantity_do_not_move_stock(self):
        material = Material.objects.create(nome='PLA', categoria='Filamento', quantidade='100', unidade='g', fonte='Lab')
        task = save_task(actor=self.admin, data={'agendamento_servico': self.booking, 'responsavel': self.owner,
            'descricao': 'Produzir peça', 'equipamento': Equipamento.objects.first(), 'material_gasto': material,
            'quantidade_material_gasto': '20 g'})
        self.assertEqual(task.servico.titulo, 'Projeto')
        self.assertEqual(task.quantidade_material_gasto, '20 g')
        material.refresh_from_db()
        self.assertEqual(str(material.quantidade), '100.000')

    def test_cancelled_booking_can_be_retained_but_not_newly_assigned(self):
        task = save_task(actor=self.admin, data={'agendamento_servico': self.booking, 'responsavel': self.owner, 'descricao': 'Inicial'})
        cancel_booking(actor=self.admin, category='servico', booking_id=self.booking.pk, expected_version=1)
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'descricao': 'Corrigida'})
        self.assertEqual(task.agendamento_servico_id, self.booking.pk)
        with self.assertRaises(ValidationError):
            save_task(actor=self.admin, data={'agendamento_servico': self.booking, 'responsavel': self.owner, 'descricao': 'Outra'})
