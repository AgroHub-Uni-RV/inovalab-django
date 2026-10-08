from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from rest_framework.test import APIClient

from inovalab_app.agenda.models import AgendaServico
from inovalab_app.agenda.services import BookingConflict, cancel_booking, review_booking, save_booking
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tests.agenda.helpers import service_data, service_web_data


class ServiceConfirmationTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin-confirmacao')
        cls.owner = get_user_model().objects.create_user('responsavel-confirmacao', is_staff=True)
        cls.external = get_user_model().objects.create_user('solicitante-confirmacao')

    def setUp(self):
        self.client.force_login(self.admin)
        self.booking = save_booking(actor=self.external, data=service_data())
        self.path = f'/tarefas/confirmar-servico/{self.booking.pk}/'

    def task_data(self, **overrides):
        return {'descricao': 'Executar o serviço solicitado', 'responsaveis': [self.owner], **overrides}

    def web_data(self, **overrides):
        return {'agendamento_versao': 1, 'descricao': 'Executar o serviço solicitado',
                'responsaveis': [self.owner.pk], 'materiais-TOTAL_FORMS': '1',
                'materiais-INITIAL_FORMS': '0', 'materiais-0-material': '',
                'materiais-0-quantidade': '', **overrides}

    def confirm(self, **overrides):
        return review_booking(actor=self.admin, category='servico', booking_id=self.booking.pk,
                              expected_version=1, decision='aprovar', task_data=self.task_data(**overrides))

    def test_admin_creation_is_pending_without_task(self):
        booking = save_booking(actor=self.admin, data=service_data())
        self.assertEqual((booking.situacao, booking.versao), ('pendente', 1))
        self.assertIsNone(booking.avaliado_em)
        self.assertFalse(booking.tarefas.exists())

    def test_confirmation_without_task_is_rejected_at_domain_boundary(self):
        with self.assertRaises(ValidationError):
            review_booking(actor=self.admin, category='servico', booking_id=self.booking.pk,
                           expected_version=1, decision='aprovar')
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.situacao, self.booking.versao, self.booking.eventos.count()), ('pendente', 1, 1))

    def test_confirmation_creates_task_with_inherited_deadline_and_both_histories(self):
        saved = self.confirm()
        task = saved.tarefas.get()
        self.assertEqual((saved.situacao, saved.versao, saved.criado_por_id), ('confirmado', 2, self.external.pk))
        self.assertEqual(saved.avaliado_por_id, self.admin.pk)
        self.assertIsNotNone(saved.avaliado_em)
        self.assertEqual((task.status, task.versao, task.prazo), ('demanda', 1, saved.servico.prazo))
        self.assertEqual(list(task.responsaveis.all()), [self.owner])
        self.assertEqual(task.eventos.get().acao, 'criar')
        self.assertEqual(saved.eventos.first().acao, 'aprovar')

    def test_invalid_task_rolls_back_confirmation_and_events(self):
        for data in ({'responsaveis': []}, {'descricao': ' '}, {'status': 'concluido'}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                self.confirm(**data)
            self.booking.refresh_from_db()
            self.assertEqual((self.booking.situacao, self.booking.versao, self.booking.eventos.count()), ('pendente', 1, 1))
            self.assertFalse(Tarefa.objects.exists())

    def test_failure_recording_approval_rolls_back_created_task_and_links(self):
        with patch('inovalab_app.agenda.services._record', side_effect=RuntimeError('falha no histórico')):
            with self.assertRaises(RuntimeError):
                self.confirm()
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.situacao, self.booking.versao), ('pendente', 1))
        self.assertFalse(Tarefa.objects.exists())
        self.assertEqual(self.booking.eventos.count(), 1)

    def test_repeat_or_stale_confirmation_never_duplicates_task(self):
        self.confirm()
        with self.assertRaises(BookingConflict):
            self.confirm()
        self.assertEqual(self.booking.tarefas.count(), 1)
        self.assertEqual(self.booking.eventos.count(), 2)

    def test_changed_pending_booking_rejects_old_task_form_without_partial_save(self):
        save_booking(actor=self.admin, category='servico', booking_id=self.booking.pk,
                     expected_version=1, data={'descricao': 'Pedido atualizado'})
        response = self.client.post(self.path, self.web_data(), HTTP_X_TASK_MODAL='1')
        self.assertEqual(response.status_code, 409)
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.situacao, self.booking.versao), ('pendente', 2))
        self.assertFalse(self.booking.tarefas.exists())
        self.assertEqual(self.booking.eventos.count(), 2)

    def test_cancelled_request_cannot_be_confirmed_from_open_task_form(self):
        cancel_booking(actor=self.external, category='servico', booking_id=self.booking.pk, expected_version=1)
        self.assertEqual(self.client.post(self.path, self.web_data()).status_code, 404)
        self.booking.refresh_from_db()
        self.assertIsNotNone(self.booking.cancelado_em)
        self.assertFalse(self.booking.tarefas.exists())

    def test_confirmation_preserves_multiple_responsibles_equipment_and_material_quantities(self):
        materials = [Material.objects.create(nome=f'Material {index}', categoria='Teste', quantidade=100,
                     unidade='g', fonte='Lab') for index in range(2)]
        equipment = list(Equipamento.objects.all()[:2])
        saved = self.confirm(responsaveis=[self.owner, self.admin], equipamentos=equipment,
            materiais_gastos=[{'material': material, 'quantidade': f'{index + 1} peças'}
                              for index, material in enumerate(materials)])
        task = saved.tarefas.get()
        self.assertEqual(set(task.responsaveis.all()), {self.owner, self.admin})
        self.assertEqual(set(task.equipamentos.all()), set(equipment))
        self.assertEqual(set(task.materiais_gastos.values_list('material_id', 'quantidade')),
                         {(materials[0].pk, '1 peças'), (materials[1].pk, '2 peças')})

    def test_get_and_invalid_form_leave_booking_pending_and_keep_input(self):
        response = self.client.get(self.path, HTTP_X_TASK_MODAL='1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Criar tarefa e confirmar agendamento')
        self.assertContains(response, 'data-task-modal-content')
        self.assertContains(response, 'disabled')
        response = self.client.post(self.path, self.web_data(responsaveis=[]), HTTP_X_TASK_MODAL='1')
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Executar o serviço solicitado', status_code=400)
        self.booking.refresh_from_db()
        self.assertEqual((self.booking.situacao, self.booking.versao), ('pendente', 1))
        self.assertFalse(Tarefa.objects.exists())

    def test_web_success_and_repeat_save(self):
        response = self.client.post(self.path, self.web_data(), HTTP_X_TASK_MODAL='1')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['saved'])
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.situacao, 'confirmado')
        self.assertEqual(self.booking.tarefas.count(), 1)
        response = self.client.post(self.path, self.web_data(), HTTP_X_TASK_MODAL='1')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.booking.tarefas.count(), 1)

    def test_web_service_binding_cannot_be_replaced(self):
        other = save_booking(actor=self.external, data=service_data())
        response = self.client.post(self.path, self.web_data(agendamento_servico=other.pk))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Tarefa.objects.exists())
        self.booking.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((self.booking.situacao, other.situacao), ('pendente', 'pendente'))

    def test_opening_an_already_confirmed_form_returns_readable_conflict(self):
        self.confirm()
        response = self.client.get(self.path, HTTP_X_TASK_MODAL='1')
        self.assertContains(response, 'Esta solicitação já foi avaliada', status_code=409)
        self.assertEqual(self.booking.tarefas.count(), 1)

    def test_technical_admin_cannot_skip_task_by_adding_service_booking(self):
        self.assertEqual(self.client.get('/admin/inovalab_app/agendaservico/add/').status_code, 403)

    def test_admin_creation_explains_required_next_step(self):
        response = self.client.get('/agenda/novo/', {'categoria': 'servico'})
        self.assertContains(response, 'Continuar para tarefa')

    def test_web_and_api_require_admin_and_csrf(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.client.post(self.path, self.web_data()).status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(self.path, self.web_data()).status_code, 403)
        api = APIClient()
        api.force_login(self.owner)
        response = api.post(f'/api/v1/agendamentos/servico/{self.booking.pk}/confirmar/',
                            {'versao': 1, 'tarefa': {'descricao': 'Executar', 'responsaveis': [self.owner.pk]}}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_confirmation_button_opens_task_form_without_confirming(self):
        response = self.client.post(f'/agenda/servico/{self.booking.pk}/avaliar/', {'decisao': 'aprovar', 'versao': 1})
        self.assertRedirects(response, self.path)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.situacao, 'pendente')
        self.assertFalse(Tarefa.objects.exists())

    def test_admin_create_continues_to_task_in_plain_and_modal_flow(self):
        for headers in ({}, {'HTTP_X_BOOKING_MODAL': '1'}):
            response = self.client.post('/agenda/novo/', service_web_data(), **headers)
            booking = AgendaServico.objects.latest('pk')
            expected = f'/tarefas/confirmar-servico/{booking.pk}/'
            if headers:
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()['next_url'], expected)
            else:
                self.assertRedirects(response, expected)
            self.assertEqual(booking.situacao, 'pendente')

    def test_api_creates_pending_then_confirms_only_with_valid_task(self):
        api = APIClient()
        api.force_login(self.admin)
        created = api.post('/api/v1/agendamentos/', service_data(prazo='2099-11-01T15:00:00-03:00'), format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['situacao'], 'pendente')
        url = f'/api/v1/agendamentos/servico/{created.data["id"]}/confirmar/'
        self.assertEqual(api.post(url, {'versao': 1}, format='json').status_code, 400)
        response = api.post(url, {'versao': 1, 'tarefa': {'descricao': 'Executar', 'responsaveis': [self.owner.pk]}}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['situacao'], 'confirmado')
        self.assertEqual(Tarefa.objects.get().agendamento_servico_id, created.data['id'])
        self.assertEqual(api.post(url, {'versao': 1, 'tarefa': {'descricao': 'Executar', 'responsaveis': [self.owner.pk]}}, format='json').status_code, 409)

    def test_api_invalid_task_and_protected_fields_never_confirm(self):
        api = APIClient()
        api.force_login(self.admin)
        url = f'/api/v1/agendamentos/servico/{self.booking.pk}/confirmar/'
        for invalid in ({'responsaveis': []}, {'status': 'concluido'}, {'prazo': '2099-01-01T10:00:00Z'},
                        {'agendamento_servico': self.booking.pk}, {'versao': 1}, {'descricao': ''}):
            with self.subTest(invalid=invalid):
                response = api.post(url, {'versao': 1, 'tarefa': {
                    'descricao': 'Executar', 'responsaveis': [self.owner.pk], **invalid}}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.booking.refresh_from_db()
                self.assertEqual((self.booking.situacao, self.booking.versao), ('pendente', 1))
                self.assertFalse(self.booking.tarefas.exists())
