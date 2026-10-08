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

class BookingCreateFlowTests(RequestFixtures, TestCase):
    def setUp(self): self.client.force_login(self.admin)

    def test_selection_offers_visit_and_service_without_equipment(self):
        response=self.client.get('/agenda/novo/')
        self.assertContains(response, '?categoria=servico')
        self.assertContains(response, '/agenda/visitas/novo/')
        self.assertNotContains(response, '?categoria=equipamento')

    def test_removed_category_is_rejected_without_writing(self):
        self.assertEqual(self.client.get('/agenda/novo/?categoria=equipamento').status_code, 400)
        response=self.client.post('/agenda/novo/', service_web_data(categoria='equipamento'))
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(AgendaServico.objects.exists())

    def test_get_form_and_selection_do_not_create_records(self):
        self.client.get('/agenda/novo/')
        self.client.get('/agenda/novo/?categoria=servico')
        self.assertFalse(AgendaServico.objects.exists())

    def test_invalid_confirmation_keeps_draft(self):
        response=self.client.post('/agenda/novo/', service_web_data(prazo_hora=''))
        self.assertEqual(response.context['form']['titulo'].value(), 'Projeto de teste')
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(AgendaServico.objects.exists())

    def test_edit_cannot_change_existing_category(self):
        booking=self.create()
        response=self.client.post(f'/agenda/servico/{booking.pk}/editar/', service_web_data(versao=1,categoria='visita'))
        self.assertTrue(response.context['form'].errors)
        booking.refresh_from_db(); self.assertEqual(booking.versao,1)
