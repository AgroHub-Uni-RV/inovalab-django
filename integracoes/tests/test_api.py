from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico
from agenda.services import cancel_booking, save_booking
from catalogo.models import Equipamento, Servico
from integracoes.models import PedidoIntegracao
from integracoes.services import create_client, rotate_credential, update_client


class IntegrationAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Impressora')

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.integration, self.token = create_client(actor=self.admin, name='AgroHub')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        self.url = '/api/v1/integracoes/agendamentos/'
        self.data = {'id_externo': '001', 'requerente_id': 'pessoa-45', 'requerente': 'Ana', 'motivo': 'Protótipo',
                     'categoria': 'servico', 'objeto': self.service.pk,
                     'inicio': '2026-11-01T14:00:00-03:00', 'fim': '2026-11-01T15:00:00-03:00'}

    def post(self, **overrides):
        return self.client.post(self.url, {**self.data, **overrides}, format='json')

    def test_external_catalog_no_longer_offers_spaces(self):
        response = self.client.get('/api/v1/integracoes/catalogo/', {'categoria': 'espaco'})
        self.assertEqual(response.status_code, 400)
        for room_id in (1, 42):
            with self.subTest(room=room_id):
                self.assertEqual(self.post(categoria='espaco', objeto=room_id).status_code, 400)
        self.assertFalse(AgendaServico.objects.exists())
        self.assertFalse(PedidoIntegracao.objects.exists())

    def test_business_admin_cannot_book_spaces_internally(self):
        self.client.credentials()
        self.client.force_login(self.admin)
        self.client.get('/agenda/novo/')
        for room_id in (1, 42):
            data = {key: value for key, value in self.data.items()
                    if key not in ('id_externo', 'requerente_id', 'requerente')}
            response = self.client.post('/api/v1/agendamentos/',
                {**data, 'categoria': 'espaco', 'objeto': room_id}, format='json',
                HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
            self.assertEqual(response.status_code, 400, response.data)

    def test_real_bearer_without_session_or_csrf_creates_and_replays(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(set(response.data), {'id', 'categoria', 'id_externo', 'repetido', 'cancelado', 'versao'})
        repeated = self.post()
        self.assertEqual((repeated.status_code, repeated.data['id'], repeated.data['repetido']), (200, response.data['id'], True))
        self.assertEqual(((AgendaServico.objects.count() + AgendaEquipamento.objects.count()), PedidoIntegracao.objects.count()), (1, 1))

    def test_missing_wrong_malformed_or_revoked_token_are_401_with_challenge(self):
        for header in ('', 'Bearer errado', 'Basic errado', 'Bearer ' + self.token + 'a', 'Bearer ' + self.token + ' extra'):
            self.client.credentials(HTTP_AUTHORIZATION=header)
            response = self.post()
            self.assertEqual(response.status_code, 401)
            self.assertTrue(response['WWW-Authenticate'].startswith('Bearer'))
        update_client(actor=self.admin, client_id=self.integration.pk, expected_version=1, data={'ativo': False})
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        self.assertEqual(self.post().status_code, 401)
        self.assertFalse(AgendaServico.objects.exists())

    def test_internal_session_does_not_authenticate_external_api_and_external_token_does_not_authenticate_internal_api(self):
        internal = APIClient()
        internal.force_login(self.admin)
        self.assertEqual(internal.post(self.url, self.data, format='json').status_code, 401)
        for url in ('/api/v1/agendamentos/', '/api/v1/me/', '/api/v1/servicos/', '/api/v1/tarefas/'):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_conflicting_idempotency_and_overlap_are_distinct_409_codes(self):
        self.assertEqual(self.post().status_code, 201)
        conflict = self.post(motivo='Outro')
        self.assertEqual((conflict.status_code, conflict.data['code']), (409, 'idempotencia_conflitante'))
        overlap = self.post(id_externo='002')
        self.assertEqual((overlap.status_code, overlap.data['code']), (409, 'horario_ocupado'))
        self.assertEqual(PedidoIntegracao.objects.count(), 1)

    def test_replay_normalizes_timezone_and_returns_current_cancelled_state_without_recreation(self):
        response = self.post()
        replay = self.post(inicio='2026-11-01T17:00:00Z', fim='2026-11-01T18:00:00Z', motivo='  Protótipo  ')
        self.assertEqual(replay.status_code, 200)
        booking_id = response.data['id']
        save_booking(actor=self.admin, category='servico', booking_id=booking_id, expected_version=1, data={'motivo': 'Local'})
        cancel_booking(actor=self.admin, category='servico', booking_id=booking_id, expected_version=2)
        replay = self.post()
        self.assertEqual((replay.status_code, replay.data['id'], replay.data['cancelado'], replay.data['versao']), (200, booking_id, True, 3))
        self.assertEqual((AgendaServico.objects.count() + AgendaEquipamento.objects.count()), 1)

    def test_clients_have_separate_external_id_namespaces(self):
        first = self.post()
        other, token = create_client(actor=self.admin, name='Outro')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        second = self.post(categoria='equipamento', objeto=self.equipment.pk)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual((first.data['categoria'], first.data['id']), (second.data['categoria'], second.data['id']))
        self.assertEqual(PedidoIntegracao.objects.count(), 2)

    def test_strict_required_json_text_ids_dates_and_protected_fields(self):
        for field in self.data:
            missing = {key: value for key, value in self.data.items() if key != field}
            self.assertEqual(self.client.post(self.url, missing, format='json').status_code, 400)
        for fields in ({'id_externo': 1}, {'requerente_id': True}, {'id_externo': 'A' * 151}, {'objeto': True},
                       {'objeto': '1'}, {'objeto': 1.5}, {'objeto': 10**100}, {'fim': self.data['inicio']},
                       {'inicio': '2026-11-01T14:00:00'}, {'requerente': ' '}, {'categoria': 'inexistente'}):
            self.assertEqual(self.post(**fields).status_code, 400)
        for field in ('versao', 'cliente', 'origem', 'criado_por', 'cancelado_em', 'servico', 'token_digest'):
            self.assertEqual(self.post(**{field: 1}).status_code, 400)
        self.assertEqual(self.client.post(self.url, [], format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 415)
        self.assertFalse(AgendaServico.objects.exists())

    def test_external_reservations_are_post_only_without_private_list_detail_or_history(self):
        created = self.post()
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.patch(self.url, {'versao': 1}, format='json').status_code, 405)
        self.assertEqual(self.client.delete(self.url, {}, format='json').status_code, 405)
        self.assertEqual(self.client.get(self.url + f'{created.data["id"]}/').status_code, 404)
        self.assertEqual(self.client.get(self.url + f'{created.data["id"]}/historico/').status_code, 404)

    def test_catalog_is_authenticated_read_only_filtered_and_paginated_with_minimal_fields(self):
        for index in range(26):
            Equipamento.objects.create(nome=f'Equipamento {index}')
        self.equipment.status = 'ocupado'
        self.equipment.save()
        Equipamento.objects.create(nome='Não expor', status='indisponivel')
        url = '/api/v1/integracoes/catalogo/'
        response = self.client.get(url, {'categoria': 'equipamento'})
        self.assertEqual((response.status_code, response.data['count'], len(response.data['results'])), (200, 33, 25))
        self.assertEqual(set(response.data['results'][0]), {'id', 'categoria', 'nome'})
        self.assertEqual(len(self.client.get(url, {'categoria': 'equipamento', 'page': 2}).data['results']), 8)
        for query in ({}, {'categoria': 'qualquer'}):
            self.assertEqual(self.client.get(url, query).status_code, 400)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 405)
        self.client.credentials()
        self.assertEqual(self.client.get(url, {'categoria': 'servico'}).status_code, 401)

    def test_new_credential_replaces_old_without_losing_idempotency(self):
        created = self.post()
        _, token = rotate_credential(actor=self.admin, client_id=self.integration.pk, expected_version=1)
        self.assertEqual(self.post().status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        replay = self.post()
        self.assertEqual((replay.status_code, replay.data['id']), (200, created.data['id']))
