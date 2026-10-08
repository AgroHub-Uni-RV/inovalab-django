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

class BookingServiceTests(RequestFixtures, TestCase):
    def test_required_text_and_aware_deadline(self):
        for invalid in ({'titulo': ''}, {'titulo': ' '*2}, {'descricao': ''}, {'prazo': None},
                        {'prazo': datetime(2099, 1, 1)}, {'titulo': 'x'*151}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError): self.create(**invalid)
        self.assertFalse(AgendaServico.objects.exists())

    def test_trimmed_fields_and_authorship_record(self):
        booking = self.create(titulo='  Serviço  ', descricao='  Pedido  ', observacoes='  Obs  ')
        self.assertEqual((booking.objeto_nome, booking.motivo, booking.observacoes), ('Serviço', 'Pedido', 'Obs'))
        self.assertEqual(booking.eventos.get().ator_id, self.admin.pk)

    def test_protected_fields_cannot_be_spoofed(self):
        for name in ('criado_por', 'situacao', 'avaliado_por', 'cancelado_em', 'versao', 'id'):
            with self.subTest(name=name), self.assertRaises(ValidationError): self.create(**{name: 1})

    def test_inactive_and_anonymous_cannot_write(self):
        self.admin.is_active = False
        for actor in (self.admin, AnonymousUser()):
            with self.assertRaises(PermissionDenied): save_booking(actor=actor, data=service_data())

    def test_admin_reads_all_and_staff_reads_only_own(self):
        first = self.create()
        own = save_booking(actor=self.owner, data=service_data())
        self.assertEqual({row.pk for row in visible_bookings(self.admin)}, {first.pk, own.pk})
        self.assertEqual([row.pk for row in visible_bookings(self.owner)], [own.pk])
        self.assertEqual(visible_bookings(self.other), [])

    def test_cancel_is_versioned_and_preserves_data_and_history(self):
        booking = self.create()
        cancel_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=1)
        booking.refresh_from_db()
        self.assertEqual(booking.versao, 2)
        self.assertEqual(booking.servico.titulo, 'Projeto de teste')
        self.assertEqual(booking.eventos.count(), 2)

    def test_invalid_versions_and_category_change_never_mutate(self):
        booking = self.create()
        for version in (None, True, '1', 0):
            with self.assertRaises(ValidationError):
                save_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=version, data={'titulo': 'Inválido'})
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=1, data={'categoria': 'visita'})
        booking.refresh_from_db()
        self.assertEqual((booking.versao, booking.eventos.count()), (1, 1))

    def test_failed_edit_event_rolls_back_service_and_version(self):
        booking = self.create()
        with patch('inovalab_app.agenda.models.EventoAgendamento.objects.create', side_effect=RuntimeError('evento')):
            with self.assertRaises(RuntimeError):
                save_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=1, data={'titulo': 'Não salvar'})
        booking.refresh_from_db()
        self.assertEqual((booking.servico.titulo, booking.versao), ('Projeto de teste', 1))
