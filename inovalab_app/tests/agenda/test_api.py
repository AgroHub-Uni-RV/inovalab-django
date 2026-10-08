from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, Client
from rest_framework.test import APIClient
from inovalab_app.agenda.models import AgendaServico, AgendaEquipamento, AgendaVisita, EventoAgendamento
from inovalab_app.agenda.services import save_booking, review_booking, cancel_booking, BookingConflict
from inovalab_app.agenda.selectors import visible_bookings, calendar_weeks, filter_bookings
from inovalab_app.tests.agenda.helpers import service_data, service_web_data, make_booking, make_service
from inovalab_app.catalogo.models import Equipamento

class RequestFixtures:
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('gestor-fluxo')
        cls.owner = get_user_model().objects.create_user('autor-fluxo', is_staff=True)
        cls.other = get_user_model().objects.create_user('outro-fluxo', is_staff=True)

    def create(self, **overrides):
        return save_booking(actor=self.admin, data=service_data(**overrides))

class BookingApiTests(RequestFixtures, TestCase):
    def setUp(self):
        self.api = APIClient()
        self.api.force_login(self.admin)

    def test_complete_create_edit_history_cancel_contract(self):
        response = self.api.post('/api/v1/agendamentos/', service_data(prazo='2099-11-01T15:00:00-03:00'), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f'/api/v1/agendamentos/servico/{response.data["id"]}/'
        self.assertEqual(self.api.get(url).data['criado_por'], self.admin.pk)
        response = self.api.patch(url, {'titulo': 'Editado', 'versao': 1}, format='json')
        self.assertEqual((response.status_code, response.data['versao']), (200, 2))
        self.assertEqual(self.api.get(url+'historico/').data['count'], 2)
        self.assertEqual(self.api.post(url+'confirmar/', {'versao': 2,
            'tarefa': {'descricao': 'Executar', 'responsaveis': [self.owner.pk]}}, format='json').status_code, 200)
        self.assertEqual(self.api.delete(url, {'versao': 3}, format='json').status_code, 204)

    def test_anonymous_and_ordinary_user_cannot_read_internal_collection(self):
        self.api.logout()
        self.assertEqual(self.api.get('/api/v1/agendamentos/').status_code, 403)
        outside = get_user_model().objects.create_user('externo-api')
        self.api.force_login(outside)
        self.assertEqual(self.api.get('/api/v1/agendamentos/').status_code, 403)
        self.assertEqual(self.api.post('/api/v1/agendamentos/', service_data(prazo='2099-11-01T15:00:00-03:00'), format='json').status_code, 201)

    def test_strict_payload_naive_deadline_and_missing_required_fields(self):
        for fields in ({'prazo': '2099-11-01T15:00:00'}, {'titulo': ''}, {'criado_por': self.other.pk}, {'versao': 1}, {'categoria': 'equipamento'}):
            response = self.api.post('/api/v1/agendamentos/', service_data(prazo='2099-11-01T15:00:00-03:00') | fields, format='json')
            self.assertEqual(response.status_code, 400, response.data)

    def test_put_requires_complete_service_data_and_version(self):
        booking = self.create()
        url = f'/api/v1/agendamentos/servico/{booking.pk}/'
        self.assertEqual(self.api.put(url, {'versao': 1, 'titulo': 'Só título'}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(url, {'titulo': 'Sem versão'}, format='json').status_code, 400)

    def test_foreign_owner_cannot_read_edit_cancel_or_access_history(self):
        booking = self.create()
        self.api.force_login(self.other)
        url = f'/api/v1/agendamentos/servico/{booking.pk}/'
        self.assertEqual(self.api.get(url).status_code, 404)
        self.assertEqual(self.api.get(url+'historico/').status_code, 404)
        self.assertEqual(self.api.patch(url, {'versao': 1}, format='json').status_code, 403)
        self.assertEqual(self.api.delete(url, {'versao': 1}, format='json').status_code, 404)

    def test_stale_edit_and_cancel_return_409_without_partial_write(self):
        booking = self.create()
        url = f'/api/v1/agendamentos/servico/{booking.pk}/'
        self.api.patch(url, {'titulo': 'Novo', 'versao': 1}, format='json')
        self.assertEqual(self.api.post(url+'confirmar/', {'versao': 2,
            'tarefa': {'descricao': 'Executar', 'responsaveis': [self.owner.pk]}}, format='json').status_code, 200)
        self.assertEqual(self.api.patch(url, {'titulo': 'Perdido', 'versao': 1}, format='json').status_code, 409)
        self.assertEqual(self.api.delete(url, {'versao': 1}, format='json').status_code, 409)
        self.assertEqual(self.api.get(url).data['titulo'], 'Novo')

    def test_month_filters_include_deadline_at_month_start_only_in_its_month(self):
        self.create(prazo=datetime(2099, 11, 1, 3, tzinfo=dt_timezone.utc))
        self.assertEqual(self.api.get('/api/v1/agendamentos/?mes=2099-11').data['count'], 1)
        self.assertEqual(self.api.get('/api/v1/agendamentos/?mes=2099-10').data['count'], 0)

    def test_booking_and_event_pagination(self):
        for _ in range(27): self.create()
        first = self.api.get('/api/v1/agendamentos/')
        self.assertEqual((first.data['count'], len(first.data['results'])), (27, 25))
        self.assertEqual(len(self.api.get('/api/v1/agendamentos/?page=2').data['results']), 2)

    def test_csrf_is_required_for_session_write(self):
        strict = APIClient(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post('/api/v1/agendamentos/', service_data(), format='json').status_code, 403)

    def test_legacy_equipment_cannot_be_edited_in_api(self):
        equipment = Equipamento.objects.first()
        booking = AgendaEquipamento.objects.create(equipamento=equipment, criado_por=self.admin,
            motivo='Histórico', inicio=datetime(2099, 11, 1, 9, tzinfo=dt_timezone.utc), fim=datetime(2099, 11, 1, 10, tzinfo=dt_timezone.utc))
        url = f'/api/v1/agendamentos/equipamento/{booking.pk}/'
        self.assertEqual(self.api.get(url).status_code, 200)
        self.assertEqual(self.api.patch(url, {'versao': 1}, format='json').status_code, 400)
