from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from inovalab_app.agenda.models import AgendaServico
from inovalab_app.agenda.services import BookingConflict, save_booking
from inovalab_app.catalogo.models import Equipamento


class ServiceRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('gestor-servicos')
        cls.owner = get_user_model().objects.create_user('solicitante-servicos')

    def payload(self, **overrides):
        return {'categoria': 'servico', 'titulo': 'Produzir protótipo', 'descricao': 'Peça para projeto',
                'prazo': datetime(2099, 12, 1, 0, 0, tzinfo=dt_timezone.utc), **overrides}

    def test_each_request_owns_an_independent_service_even_with_same_deadline(self):
        first = save_booking(actor=self.admin, data=self.payload())
        second = save_booking(actor=self.admin, data=self.payload())
        self.assertNotEqual(first.servico_id, second.servico_id)
        self.assertEqual(first.servico.titulo, 'Produzir protótipo')
        self.assertEqual(first.eventos.get().acao, 'criar')
        self.assertEqual(first.situacao, 'pendente')

    def test_normal_request_is_pending_and_preserves_authorship(self):
        booking = save_booking(actor=self.owner, data=self.payload())
        self.assertEqual((booking.criado_por_id, booking.situacao, booking.versao), (self.owner.pk, 'pendente', 1))

    def test_equipment_booking_is_rejected_at_domain_boundary(self):
        equipment = Equipamento.objects.first()
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, data={'categoria': 'equipamento', 'objeto': equipment.pk,
                'motivo': 'Uso', 'inicio': datetime(2099, 1, 1, 9, tzinfo=dt_timezone.utc),
                'fim': datetime(2099, 1, 1, 10, tzinfo=dt_timezone.utc)})

    def test_request_api_accepts_new_contract_and_rejects_old_fields(self):
        api = APIClient()
        api.force_login(self.owner)
        payload = self.payload(prazo='2099-12-01T17:00:00-03:00')
        response = api.post('/api/v1/agendamentos/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['titulo'], 'Produzir protótipo')
        response = api.post('/api/v1/agendamentos/', {**payload, 'material_proprio': True}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_modal_and_plain_form_use_separate_deadline_fields(self):
        self.client.force_login(self.owner)
        response = self.client.get('/agenda/novo/?categoria=servico', HTTP_X_BOOKING_MODAL='1')
        self.assertContains(response, 'name="prazo_data"')
        self.assertContains(response, 'name="prazo_hora"')
        self.assertNotContains(response, 'name="objeto"')
        response = self.client.post('/agenda/novo/', {'categoria': 'servico', 'titulo': 'Pedido local',
            'descricao': 'Descrição local', 'prazo_data': '2099-12-01', 'prazo_hora': '17:00'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/agenda/meus/'))

    def test_stale_update_does_not_change_service_or_create_event(self):
        booking = save_booking(actor=self.admin, data=self.payload())
        save_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=1,
                     data={'titulo': 'Novo título'})
        with self.assertRaises(BookingConflict):
            save_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=1,
                         data={'titulo': 'Sobrescrito'})
        booking.refresh_from_db()
        self.assertEqual(booking.servico.titulo, 'Novo título')
        self.assertEqual(booking.eventos.count(), 2)

    def test_failed_event_rolls_back_service_and_booking(self):
        with patch('inovalab_app.agenda.models.EventoAgendamento.objects.create', side_effect=RuntimeError('evento')):
            with self.assertRaises(RuntimeError):
                save_booking(actor=self.admin, data=self.payload())
        self.assertEqual(AgendaServico.objects.count(), 0)
