from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico
from agenda.services import save_booking
from catalogo.models import Equipamento, Servico


class BookingAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('comum', is_staff=True)
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Impressora')

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.admin)
        self.url = '/api/v1/agendamentos/'
        self.data = {'categoria': 'servico', 'objeto': self.service.pk, 'motivo': 'Protótipo',
                     'inicio': '2026-11-01T14:00:00-03:00', 'fim': '2026-11-01T15:00:00-03:00'}

    def create(self, **overrides):
        response = self.client.post(self.url, {**self.data, **overrides}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_session_admin_without_staff_can_crud_and_history(self):
        booking = self.create()
        url = f'{self.url}{booking["categoria"]}/{booking["id"]}/'
        self.assertEqual((booking['objeto_nome'], booking['versao']), (self.service.nome, 1))
        response = self.client.patch(url, {'versao': 1, 'motivo': 'Corrigido'}, format='json')
        self.assertEqual((response.status_code, response.data['versao']), (200, 2))
        history = self.client.get(url + 'historico/').data
        self.assertEqual(history['count'], 2)
        self.assertEqual(history['results'][0]['alteracoes'], {'motivo': {'anterior': 'Protótipo', 'novo': 'Corrigido'}})
        self.assertEqual(self.client.delete(url, {'versao': 2}, format='json').status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url + 'historico/').status_code, 404)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(AgendaServico.objects.get(pk=booking['id']).eventos.count(), 3)
        self.create()

    def test_resource_categories_are_supported(self):
        for category, target in (('servico', self.service), ('equipamento', self.equipment)):
            booking = self.create(categoria=category, objeto=target.pk)
            self.assertEqual((booking['categoria'], booking['objeto']), (category, target.pk))

    def test_anonymous_denied_and_normal_user_can_only_read_own_or_create_pending(self):
        booking = self.create()
        self.client.logout()
        for suffix in ('', f'{booking["categoria"]}/{booking["id"]}/', f'{booking["categoria"]}/{booking["id"]}/historico/'):
            self.assertEqual(self.client.get(self.url + suffix).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data, format='json').status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        for suffix in (f'{booking["categoria"]}/{booking["id"]}/', f'{booking["categoria"]}/{booking["id"]}/historico/'):
            self.assertEqual(self.client.get(self.url + suffix).status_code, 404)
        own = self.create()
        self.assertEqual(own['situacao'], 'pendente')
        for actor in (None, self.user):
            self.client.logout()
            if actor:
                self.client.force_login(actor)
            self.assertEqual(self.client.patch(f'{self.url}{booking["categoria"]}/{booking["id"]}/', {'versao': 1}, format='json').status_code, 403)
            self.assertEqual(self.client.delete(f'{self.url}{booking["categoria"]}/{booking["id"]}/', {'versao': 1}, format='json').status_code, 404 if actor else 403)

    def test_overlap_and_stale_version_are_409_without_partial_update(self):
        booking = self.create()
        response = self.client.post(self.url, self.data, format='json')
        self.assertEqual((response.status_code, response.data['code']), (409, 'horario_ocupado'))
        url = f'{self.url}{booking["categoria"]}/{booking["id"]}/'
        self.client.patch(url, {'versao': 1, 'motivo': 'Atualizado'}, format='json')
        for method in (self.client.patch, self.client.delete):
            response = method(url, {'versao': 1}, format='json')
            self.assertEqual((response.status_code, response.data['code']), (409, 'versao_desatualizada'))
        self.assertEqual(AgendaServico.objects.get(pk=booking['id']).eventos.count(), 2)

    def test_strict_payload_versions_and_object_ids(self):
        for version in (True, 1.5, '1', 0, None):
            with self.subTest(version=version):
                self.assertEqual(self.client.post(self.url, {**self.data, 'versao': version}, format='json').status_code, 400)
        for field in ('servico', 'equipamento', 'espaco', 'espaco_legado_id', 'espaco_legado_nome',
                      'criado_por', 'id', 'cancelado_em', 'objeto_nome'):
            self.assertEqual(self.client.post(self.url, {**self.data, field: 1}, format='json').status_code, 400)
        for value in (True, '1', 1.5, None, 0, 999999):
            self.assertEqual(self.client.post(self.url, {**self.data, 'objeto': value}, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url, [], format='json').status_code, 400)
        booking = self.create()
        url = f'{self.url}{booking["categoria"]}/{booking["id"]}/'
        self.assertEqual(self.client.patch(url, {'motivo': 'Sem versão'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'versao': 1, 'categoria': 'espaco'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(url, {'versao': 1, 'motivo': 'Inesperado'}, format='json').status_code, 400)

    def test_naive_invalid_or_zero_intervals_are_rejected_and_put_is_complete(self):
        for fields in ({'inicio': '2026-11-01T14:00:00'}, {'fim': self.data['inicio']}, {'fim': 'inválido'}, {'requerente': ' '}):
            self.assertEqual(self.client.post(self.url, {**self.data, **fields}, format='json').status_code, 400)
        booking = self.create()
        url = f'{self.url}{booking["categoria"]}/{booking["id"]}/'
        self.assertEqual(self.client.put(url, {'versao': 1, 'motivo': 'Incompleto'}, format='json').status_code, 400)
        self.assertEqual(self.client.put(url, {**self.data, 'versao': 1}, format='json').status_code, 200)

    def test_unavailable_target_is_400_but_unchanged_metadata_remains_editable(self):
        booking = self.create()
        self.service.status = 'indisponivel'
        self.service.save()
        self.assertEqual(self.client.post(self.url, self.data, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'{self.url}{booking["categoria"]}/{booking["id"]}/', {'versao': 1, 'motivo': 'Só descrição'}, format='json').status_code, 200)

    def test_filters_include_cross_month_reservations_and_exclude_end_at_month_start(self):
        self.create(inicio='2026-10-31T23:00:00-03:00', fim='2026-11-01T01:00:00-03:00')
        other = Servico.objects.create(nome='Outro serviço')
        self.create(objeto=other.pk, inicio='2026-10-31T20:00:00-03:00', fim='2026-11-01T00:00:00-03:00')
        self.create(categoria='equipamento', objeto=self.equipment.pk)
        response = self.client.get(self.url, {'mes': '2026-11', 'categoria': 'servico'})
        self.assertEqual((response.status_code, response.data['count']), (200, 1))
        self.assertEqual(self.client.get(self.url).data['count'], 3)
        for fields in ({'mes': '2026-13'}, {'mes': '2026-1'}, {'categoria': 'qualquer'}, {'mes': '9999-12'}):
            self.assertEqual(self.client.get(self.url, fields).status_code, 400)

    def test_booking_and_history_pagination(self):
        start = datetime.fromisoformat(self.data['inicio'])
        for index in range(26):
            self.create(inicio=(start + timedelta(hours=index)).isoformat(), fim=(start + timedelta(hours=index + 1)).isoformat())
        page = self.client.get(self.url).data
        self.assertEqual((page['count'], len(page['results'])), (26, 25))
        self.assertEqual(len(self.client.get(self.url, {'page': 2}).data['results']), 1)
        booking = AgendaServico.objects.first()
        for version in range(1, 27):
            save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=version, data={'motivo': str(version)})
        page = self.client.get(f'{self.url}{booking.categoria}/{booking.pk}/historico/').data
        self.assertEqual((page['count'], len(page['results'])), (27, 25))

    def test_session_authentication_requires_csrf_for_unsafe_requests(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url, self.data, format='json').status_code, 403)
        client.get('/agenda/novo/')
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.url, self.data, format='json', HTTP_X_CSRFTOKEN=token).status_code, 201)
