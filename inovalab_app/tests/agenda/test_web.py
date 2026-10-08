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

class BookingWebTests(RequestFixtures, TestCase):
    def setUp(self): self.client.force_login(self.admin)

    def test_admin_creates_edits_and_reads_service(self):
        response = self.client.post('/agenda/novo/', service_web_data())
        self.assertEqual(response.status_code, 302)
        booking = AgendaServico.objects.get()
        self.assertContains(self.client.get(response.url), 'Projeto de teste')
        self.assertContains(self.client.get(response.url), 'Prazo')
        self.assertEqual(self.client.post(f'/agenda/servico/{booking.pk}/editar/', service_web_data(titulo='Editado', versao=1)).status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.servico.titulo, 'Editado')

    def test_invalid_and_spoofed_form_fields_do_not_persist(self):
        for invalid in ({'titulo': ''}, {'descricao': ''}, {'prazo_hora': '25:00'}, {'criado_por': self.other.pk}):
            response = self.client.post('/agenda/novo/', service_web_data(**invalid))
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(AgendaServico.objects.exists())

    def test_stale_edit_returns_409_and_preserves_new_title(self):
        booking = self.create()
        url = f'/agenda/servico/{booking.pk}/editar/'
        self.client.post(url, service_web_data(titulo='Novo', versao=1))
        self.assertEqual(self.client.post(url, service_web_data(titulo='Perdido', versao=1)).status_code, 409)
        booking.refresh_from_db()
        self.assertEqual(booking.servico.titulo, 'Novo')

    def test_minute_edit_preserves_unchanged_subsecond_deadline(self):
        deadline = datetime(2099, 11, 1, 18, 0, 37, 123456, tzinfo=dt_timezone.utc)
        booking = self.create(prazo=deadline)
        self.client.post(f'/agenda/servico/{booking.pk}/editar/', service_web_data(titulo='Outro', versao=1))
        booking.refresh_from_db()
        self.assertEqual(booking.servico.prazo, deadline)

    def test_changed_deadline_is_saved_in_minutes(self):
        booking = self.create(prazo=datetime(2099, 11, 1, 18, 0, 37, tzinfo=dt_timezone.utc))
        self.client.post(f'/agenda/servico/{booking.pk}/editar/', service_web_data(prazo_hora='16:01:42', versao=1))
        booking.refresh_from_db()
        self.assertEqual((booking.servico.prazo.hour, booking.servico.prazo.minute, booking.servico.prazo.second), (19, 1, 0))

    def test_csrf_and_get_cancel_do_not_change_service(self):
        booking = self.create()
        strict = Client(enforce_csrf_checks=True); strict.force_login(self.admin)
        url = f'/agenda/servico/{booking.pk}/cancelar/'
        self.assertEqual(strict.get(url).status_code, 200)
        self.assertEqual(strict.post(url, {'versao': 1}).status_code, 403)
        booking.refresh_from_db(); self.assertIsNone(booking.cancelado_em)

    def test_history_is_paginated_and_detail_is_scoped(self):
        booking = self.create()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/agenda/servico/{booking.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/agenda/servico/{booking.pk}/historico/').status_code, 404)

    def test_search_matches_creator_title_and_description(self):
        booking = self.create(titulo='Projeto pesquisável', descricao='Conteúdo pesquisável')
        for query in ('gestor-fluxo', 'Projeto pesquisável', 'Conteúdo pesquisável'):
            response = self.client.get('/agenda/', {'q': query, 'mes': '2099-11'})
            self.assertEqual([row.pk for row in response.context['object_list']], [booking.pk])
