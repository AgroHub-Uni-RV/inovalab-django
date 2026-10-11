from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, Client, override_settings
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
        booking = save_booking(actor=self.admin, data=service_data(**overrides))
        return review_booking(actor=self.admin, category='servico', booking_id=booking.pk,
            expected_version=1, decision='aprovar', task_data={'descricao': 'Executar', 'responsaveis': [self.owner]})

class AgendaFrontendTests(RequestFixtures, TestCase):
    @override_settings(TIME_ZONE='America/Sao_Paulo')
    @patch('django.utils.timezone.now', return_value=datetime(2026, 11, 1, 1, 30, tzinfo=dt_timezone.utc))
    def test_today_uses_local_date_at_utc_month_boundary(self, now):
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/', {'mes': '2026-10'})
        marked = [day for week in response.context['weeks'] for day in week if day['is_today']]
        self.assertEqual([str(day['date']) for day in marked], ['2026-10-31'])
        self.assertContains(response, 'aria-current="date"', count=1)
        self.assertContains(response, '<span class="agenda-today-label">Hoje</span>', count=1, html=True)
        self.assertContains(response, '<span class="swatch event" aria-hidden="true"></span>Evento', html=True)
        self.assertContains(response, '<span class="swatch recess" aria-hidden="true"></span>Recesso', html=True)
        self.assertContains(response, '<span class="swatch holiday" aria-hidden="true"></span>Feriado', html=True)

    @override_settings(TIME_ZONE='America/Sao_Paulo')
    @patch('django.utils.timezone.now', return_value=datetime(2026, 10, 1, 1, 30, tzinfo=dt_timezone.utc))
    def test_today_is_marked_in_adjacent_month_cells_but_not_distant_months(self, now):
        self.client.force_login(self.admin)
        adjacent = self.client.get('/agenda/', {'mes': '2026-10'})
        marked = [day for week in adjacent.context['weeks'] for day in week if day['is_today']]
        self.assertEqual([str(day['date']) for day in marked], ['2026-09-30'])
        self.assertFalse(marked[0]['in_month'])
        self.assertContains(adjacent, 'aria-current="date"', count=1)
        distant = self.client.get('/agenda/', {'mes': '2026-12'})
        self.assertFalse(any(day['is_today'] for week in distant.context['weeks'] for day in week))
        self.assertNotContains(distant, 'aria-current="date"')

    def test_deadline_at_midnight_marks_only_one_correct_calendar_day(self):
        booking=self.create(prazo=datetime(2099,11,1,3,tzinfo=dt_timezone.utc))
        days=[day for week in calendar_weeks([booking],'2099-11') for day in week if day['count']]
        self.assertEqual([(str(day['date']),day['count']) for day in days],[('2099-11-01',1)])

    def test_calendar_contains_all_bookings_independent_of_table_pagination(self):
        for _ in range(27): self.create()
        self.client.force_login(self.admin)
        response=self.client.get('/agenda/',{'mes':'2099-11'})
        self.assertEqual(len(response.context['object_list']),25)
        self.assertEqual(sum(day['count'] for week in response.context['weeks'] for day in week),27)

    def test_cancelled_and_pending_do_not_appear_as_calendar_reservations(self):
        confirmed=self.create()
        pending=save_booking(actor=self.owner,data=service_data())
        cancel_booking(actor=self.admin,category='servico',booking_id=confirmed.pk,expected_version=2)
        confirmed.refresh_from_db()
        self.assertEqual(sum(day['count'] for week in calendar_weeks([confirmed,pending],'2099-11') for day in week),0)

    def test_service_detail_shows_description_and_deadline_without_material_fields(self):
        booking=self.create()
        self.client.force_login(self.admin)
        response=self.client.get(f'/agenda/servico/{booking.pk}/')
        self.assertContains(response,'Descrição do pedido')
        self.assertContains(response,'Prazo')
        self.assertNotContains(response,'Tem material próprio?')
