from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from agenda.models import AgendaServico, AgendaEquipamento, EventoAgendamento
from agenda.services import save_booking


class RemoteOnlyVisitBoundaryTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('gestor-visitas')
        self.client = APIClient()
        self.client.force_login(self.admin)

    def test_local_api_and_services_reject_visits_without_any_persistence(self):
        data = {'categoria': 'visita', 'inicio': '2026-11-01T14:00:00-03:00', 'fim': '2026-11-01T15:00:00-03:00'}
        response = self.client.post('/api/v1/agendamentos/', data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('categoria', response.data)
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, data=data)
        self.assertEqual((AgendaServico.objects.count(), AgendaEquipamento.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))

    def test_visit_creation_navigation_uses_remote_route(self):
        response = self.client.get('/agenda/novo/?categoria=visita')
        self.assertRedirects(response, '/agenda/visitas/novo/', fetch_redirect_response=False)
        self.assertContains(self.client.get('/agenda/novo/'), '/agenda/visitas/novo/')
