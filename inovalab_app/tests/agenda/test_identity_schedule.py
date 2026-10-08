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

class BookingIdentityScheduleTests(RequestFixtures, TestCase):
    def test_service_form_has_deadline_date_and_time(self):
        self.client.force_login(self.owner)
        form = self.client.get('/agenda/novo/?categoria=servico').context['form']
        self.assertEqual(form.fields['prazo_hora'].widget.attrs['step'], '60')
        self.assertNotIn('hora_inicio', form.fields)
        self.assertNotIn('objeto', form.fields)

    def test_timezone_correct_initial_deadline_for_edit(self):
        booking = self.create(prazo=datetime(2099, 11, 1, 1, 30, tzinfo=dt_timezone.utc))
        self.client.force_login(self.admin)
        form = self.client.get(f'/agenda/servico/{booking.pk}/editar/').context['form']
        self.assertEqual(str(form.initial['prazo_data']), '2099-10-31')
        self.assertEqual(form.initial['prazo_hora'].hour, 22)

    def test_edit_does_not_replace_original_creator(self):
        booking = save_booking(actor=self.owner, data=service_data())
        save_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=1, data={'titulo': 'Corrigido'})
        booking.refresh_from_db(); self.assertEqual(booking.criado_por_id, self.owner.pk)

    def test_api_rejects_identity_spoofing(self):
        api=APIClient(); api.force_login(self.owner)
        response=api.post('/api/v1/agendamentos/', service_data(prazo='2099-11-01T15:00:00-03:00', criado_por=self.admin.pk), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AgendaServico.objects.exists())

    def test_creator_name_survives_account_deletion_in_history(self):
        booking = save_booking(actor=self.owner, data=service_data())
        self.owner.delete(); booking.refresh_from_db()
        self.assertEqual(booking.criador_nome, 'autor-fluxo')
