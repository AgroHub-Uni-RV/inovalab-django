from inovalab_app.tests.agenda.helpers import service_data, service_web_data
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from inovalab_app.agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico
from inovalab_app.agenda.services import save_booking
from inovalab_app.catalogo.models import Equipamento, Servico


class BookingObservationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('autor-observacoes', is_staff=True)
        cls.admin = get_user_model().objects.create_superuser('editor-observacoes')
        cls.equipment = Equipamento.objects.create(nome='Sala de observações')

    def setUp(self):
        self.client.force_login(self.user)
        self.data = service_data(prazo=datetime.fromisoformat('2026-11-01T15:00:00-03:00'))
        self.web = service_web_data(prazo_data='2026-11-01', prazo_hora='15:00')

    def test_web_saves_optional_observations_and_escapes_html_in_detail(self):
        response = self.client.post('/agenda/novo/', {**self.web,
            'observacoes': '  Trazer peças\n<script>alert(1)</script>  '})
        self.assertEqual(response.status_code, 302)
        booking = AgendaServico.objects.get()
        self.assertEqual(booking.observacoes, 'Trazer peças\n<script>alert(1)</script>')
        detail = self.client.get(response.url)
        self.assertContains(detail, 'Observações')
        self.assertContains(detail, 'Trazer peças<br>')
        self.assertContains(detail, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(detail, '<script>alert(1)</script>')

    def test_omitted_or_blank_observations_are_optional(self):
        for observations in (None, '', '   '):
            payload = self.web if observations is None else {**self.web, 'observacoes': observations}
            response = self.client.post('/agenda/novo/', payload)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(AgendaServico.objects.latest('pk').observacoes, '')

    def test_admin_can_edit_and_clear_observations_with_history(self):
        booking = save_booking(actor=self.user, data={**self.data, 'observacoes': 'Original'})
        self.client.force_login(self.admin)
        url = f'/agenda/{booking.categoria}/{booking.pk}/editar/'
        self.assertEqual(self.client.get(url).context['form']['observacoes'].value(), 'Original')
        for version, before, after in [(1, 'Original', 'Correção'), (2, 'Correção', '')]:
            response = self.client.post(url, {**self.web, 'versao': version, 'observacoes': after})
            self.assertEqual(response.status_code, 302)
            booking.refresh_from_db()
            self.assertEqual(booking.observacoes, after)
            self.assertEqual(booking.criado_por_id, self.user.pk)
            self.assertEqual(booking.eventos.first().alteracoes,
                             {'observacoes': {'anterior': before, 'novo': after}})

    def test_invalid_form_preserves_unsaved_observations(self):
        response = self.client.post('/agenda/novo/', {**self.web, 'titulo': '', 'observacoes': 'Rascunho de observações'})
        self.assertEqual(response.context['form']['observacoes'].value(), 'Rascunho de observações')
        self.assertFalse(AgendaServico.objects.exists())

    def test_api_preserves_observations_on_patch_and_rejects_stale_clear(self):
        api = APIClient()
        api.force_login(self.admin)
        response = api.post('/api/v1/agendamentos/', {**self.data, 'observacoes': '  Detalhe  '}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['observacoes'], 'Detalhe')
        url = f'/api/v1/agendamentos/{response.data["categoria"]}/{response.data["id"]}/'
        response = api.patch(url, {'versao': 1, 'descricao': 'Corrigido'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['observacoes'], 'Detalhe')
        self.assertEqual(api.patch(url, {'versao': 1, 'observacoes': ''}, format='json').status_code, 409)
        response = api.patch(url, {'versao': 2, 'observacoes': ''}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['observacoes'], '')

    def test_observations_are_optional_in_service_form(self):
        response = self.client.get('/agenda/novo/', {'categoria': 'servico'})
        self.assertFalse(response.context['form'].fields['observacoes'].required)
        booking = save_booking(actor=self.user, data={**self.data, 'observacoes': '  Informação adicional  '})
        self.assertEqual(booking.observacoes, 'Informação adicional')
