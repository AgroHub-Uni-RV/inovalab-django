from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from inovalab_app.agenda.models import AgendaVisita
from inovalab_app.tests.agenda.helpers import make_booking


class ExecutionApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('api-realizacao-admin')
        cls.staff = get_user_model().objects.create_user('api-realizacao-equipe', is_staff=True)
        cls.owner = get_user_model().objects.create_user('api-realizacao-titular')

    def setUp(self):
        self.visit = AgendaVisita.objects.create(quantidade_pessoas=2, data=date(2026, 10, 8),
            hora_inicio=time(9), hora_termino=time(10), criado_por=self.owner)
        self.url = f'/api/v1/agendamentos/visita/{self.visit.pk}/'
        self.api = APIClient()
        self.api.force_login(self.admin)
        self.enterContext(patch('django.utils.timezone.now', return_value=self.visit.inicio))

    def test_realization_is_admin_post_not_patch(self):
        response = self.api.post(self.url+'realizar/', {'versao': 1}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.data['situacao'], response.data['estado_execucao'], response.data['versao']),
                         ('confirmado', 'concluido', 2))
        self.assertEqual(response.data['realizada_por'], self.admin.pk)
        self.assertFalse(response.data['atrasado'])
        self.assertEqual(self.api.post(self.url+'realizar/', {'versao': 1}, format='json').status_code, 409)
        self.assertEqual(self.api.post(self.url+'realizar/', {'versao': 2}, format='json').status_code, 409)
        for actor in (self.staff, self.owner):
            self.api.force_login(actor)
            self.assertEqual(self.api.post(self.url+'realizar/', {'versao': 2}, format='json').status_code, 403)
        self.assertEqual(self.visit.eventos.filter(acao='realizar').count(), 1)

    def test_read_only_metadata_and_strict_payload(self):
        for field in ('realizada_em', 'realizada_por', 'estado_execucao', 'atrasado', 'concluido_com_atraso',
                      'concluido_em', 'situacao'):
            response = self.api.patch(self.url, {'versao': 1, field: 'alterar'}, format='json')
            self.assertEqual(response.status_code, 400)
            payload = {'categoria': 'visita', 'quantidade_pessoas': 2, 'data': '2026-10-09',
                       'hora_inicio': '09:00', 'hora_termino': '10:00', field: 'alterar'}
            self.assertEqual(self.api.post('/api/v1/agendamentos/', payload, format='json').status_code, 400)
        self.assertEqual(self.api.post(self.url+'realizar/', {'versao': True}, format='json').status_code, 400)
        self.assertEqual(self.api.post(self.url+'realizar/', {'versao': 1, 'retorno': '/'}, format='json').status_code, 400)
        self.assertFalse(self.visit.eventos.exists())

    def test_wrong_category_and_missing_visit_never_write(self):
        booking = make_booking(actor=self.admin)
        for category in ('servico', 'equipamento'):
            response = self.api.post(f'/api/v1/agendamentos/{category}/{booking.pk}/realizar/', {'versao': 1}, format='json')
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.api.post('/api/v1/agendamentos/visita/99999/realizar/', {'versao': 1}, format='json').status_code, 404)
        self.assertFalse(self.visit.eventos.exists())

    def test_read_execution_metadata_is_additive_and_private(self):
        booking = make_booking(actor=self.staff, prazo=self.visit.inicio)
        self.api.force_login(self.staff)
        response = self.api.get('/api/v1/agendamentos/')
        self.assertEqual(response.data['count'], 1)
        record = response.data['results'][0]
        self.assertEqual((record['id'], record['situacao'], record['estado_execucao']),
                         (booking.pk, 'confirmado', 'aguardando_inicio'))
        self.assertNotIn('tarefas', record)
        self.assertEqual(self.api.get(self.url).status_code, 404)
