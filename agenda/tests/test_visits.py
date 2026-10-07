from datetime import datetime, timedelta
import hashlib
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from agenda.models import Agendamento, EventoAgendamento
from agenda.services import BookingConflict, cancel_booking, review_booking, save_booking
from catalogo.models import Equipamento
from integracoes.services import create_client
from integracoes.models import PedidoIntegracao


class VisitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('gestor')
        cls.user = get_user_model().objects.create_user('visitante', is_staff=True)
        cls.equipment = Equipamento.objects.create(nome='Impressora')
        cls.start = datetime.fromisoformat('2026-11-01T14:00:00-03:00')
        cls.end = datetime.fromisoformat('2026-11-01T15:00:00-03:00')

    def data(self, **overrides):
        return {'categoria': 'visita', 'inicio': self.start, 'fim': self.end, **overrides}

    def test_visit_without_catalog_target_records_creator_and_history(self):
        booking = save_booking(actor=self.admin, data=self.data())
        self.assertEqual((booking.categoria, booking.objeto_id, booking.objeto_nome), ('visita', None, 'Visita'))
        self.assertEqual((booking.criado_por_id, booking.motivo, booking.observacoes), (self.admin.pk, '', ''))
        self.assertEqual(booking.eventos.get().alteracoes['categoria']['novo'], 'visita')

    def test_visit_form_requires_day_times_and_people(self):
        self.client.force_login(self.user)
        response = self.client.get('/agenda/novo/?categoria=visita')
        self.assertEqual(set(response.context['form'].fields),
                         {'categoria', 'dia', 'hora_inicio', 'hora_termino', 'quantidade_pessoas', 'versao'})
        for field in ('objeto', 'motivo', 'observacoes', 'equipamentos'):
            self.assertNotContains(response, f'name="{field}"')
        response = self.client.post('/agenda/novo/', {'categoria': 'visita', 'dia': '2026-11-01',
            'hora_inicio': '14:00', 'hora_termino': '15:00', 'quantidade_pessoas': 1})
        self.assertEqual(response.status_code, 302)
        booking = Agendamento.objects.get()
        self.assertEqual((booking.inicio, booking.fim, booking.situacao), (self.start, self.end, 'pendente'))
        self.assertContains(self.client.get(response.url), 'Visita')
        self.assertNotContains(self.client.get(response.url), '<h2>Observações</h2>')

    def test_visit_rejects_catalog_and_text_fields_without_writes(self):
        for name, value in [('objeto', 42), ('motivo', 'Texto'), ('observacoes', ''),
                            ('equipamentos', []), ('material_proprio', None)]:
            with self.subTest(field=name), self.assertRaises(ValidationError):
                save_booking(actor=self.admin, data=self.data(**{name: value}))
        self.assertFalse(Agendamento.objects.exists())

    def test_visit_requires_same_local_day_and_positive_interval(self):
        for fields in ({'fim': self.start}, {'fim': self.start + timedelta(days=1)},
                       {'inicio': self.start.replace(tzinfo=None)}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                save_booking(actor=self.admin, data=self.data(**fields))
        # Different UTC dates still belong to one day in São Paulo.
        booking = save_booking(actor=self.admin, data=self.data(
            inicio=datetime.fromisoformat('2026-11-01T23:30:00+00:00'),
            fim=datetime.fromisoformat('2026-11-02T02:00:00+00:00')))
        self.assertEqual(booking.categoria, 'visita')

    def test_visit_conflict_adjacency_and_cancel_release(self):
        booking = save_booking(actor=self.admin, data=self.data())
        with self.assertRaises(BookingConflict):
            save_booking(actor=self.admin, data=self.data(inicio=self.start + timedelta(minutes=30)))
        save_booking(actor=self.admin, data=self.data(inicio=self.end, fim=self.end + timedelta(hours=1)))
        save_booking(actor=self.admin, data=self.data(categoria='equipamento', objeto=self.equipment.pk, motivo='Uso'))
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=1)
        save_booking(actor=self.admin, data=self.data())
        self.assertEqual(Agendamento.objects.filter(cancelado_em__isnull=True).count(), 3)

    def test_visit_approval_checks_confirmed_conflict(self):
        first = save_booking(actor=self.user, data=self.data())
        second = save_booking(actor=self.user, data=self.data())
        review_booking(actor=self.admin, booking_id=first.pk, expected_version=1, decision='aprovar')
        with self.assertRaises(BookingConflict):
            review_booking(actor=self.admin, booking_id=second.pk, expected_version=1, decision='aprovar')
        second.refresh_from_db()
        self.assertEqual((second.situacao, second.versao), ('pendente', 1))

    def test_visit_category_switch_clears_old_resource_details(self):
        booking = save_booking(actor=self.admin, data=self.data(categoria='equipamento',
            objeto=self.equipment.pk, motivo='Projeto', observacoes='Notas'))
        booking = save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1,
                               data={'categoria': 'visita'})
        self.assertEqual((booking.categoria, booking.equipamento_id, booking.motivo, booking.observacoes),
                         ('visita', None, '', ''))
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=2,
                         data={'categoria': 'equipamento', 'objeto': self.equipment.pk})

    def test_people_are_audited_and_cleared_when_visit_becomes_equipment(self):
        booking = save_booking(actor=self.admin, data=self.data(quantidade_pessoas=9))
        self.assertEqual(booking.eventos.get().alteracoes['quantidade_pessoas']['novo'], 9)
        booking = save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1,
                               data={'categoria': 'equipamento', 'objeto': self.equipment.pk, 'motivo': 'Uso'})
        self.assertIsNone(booking.quantidade_pessoas)
        self.assertEqual(booking.eventos.first().alteracoes['quantidade_pessoas'], {'anterior': 9, 'novo': None})

    def test_equipment_does_not_accept_people(self):
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, data=self.data(categoria='equipamento', objeto=self.equipment.pk,
                                                         motivo='Uso', quantidade_pessoas=2))
        self.assertFalse(Agendamento.objects.exists())

    def test_no_new_space_reservation_even_for_admin(self):
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, data=self.data(categoria='espaco', objeto=42, motivo='Sala'))
        api = APIClient()
        api.force_login(self.admin)
        response = api.post('/api/v1/agendamentos/', self.data(categoria='espaco', objeto=42, motivo='Sala'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Agendamento.objects.exists())

    def test_legacy_space_remains_readable_and_cancelable_but_cannot_be_renewed(self):
        booking = Agendamento.objects.create(espaco_legado_id=42, espaco_legado_nome='Sala antiga', motivo='Antigo', inicio=self.start,
            fim=self.end, criado_por=self.admin)
        EventoAgendamento.objects.create(agendamento=booking, ator=self.admin, ator_nome='gestor', acao='criar')
        self.client.force_login(self.admin)
        response = self.client.get(f'/agenda/{booking.pk}/')
        self.assertContains(response, 'legado')
        self.assertNotContains(response, 'Editar agendamento')
        listing = self.client.get('/agenda/?mes=2026-11')
        self.assertNotContains(listing, f'href="/agenda/{booking.pk}/editar/"')
        self.assertContains(self.client.get('/agenda/?mes=2026-11&q=Sala+antiga'), 'Sala antiga')
        api = APIClient()
        api.force_login(self.admin)
        payload = api.get(f'/api/v1/agendamentos/{booking.pk}/').data
        self.assertEqual((payload['categoria'], payload['objeto'], payload['objeto_nome']),
                         ('espaco', 42, 'Sala antiga'))
        self.assertEqual(self.client.get(f'/agenda/{booking.pk}/editar/').status_code, 403)
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Novo'})
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=1)
        booking.refresh_from_db()
        self.assertEqual((booking.espaco_legado_id, booking.eventos.count()), (42, 2))

    def test_api_visit_create_patch_filter_and_no_extra_fields(self):
        api = APIClient()
        api.force_login(self.admin)
        response = api.post('/api/v1/agendamentos/', self.data(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['objeto'])
        booking_id = response.data['id']
        response = api.patch(f'/api/v1/agendamentos/{booking_id}/',
                             {'versao': 1, 'fim': self.end + timedelta(minutes=10)}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(api.get('/api/v1/agendamentos/?categoria=visita').data['count'], 1)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/agenda/?mes=2026-11&categoria=visita'), 'Visita')
        response = api.patch(f'/api/v1/agendamentos/{booking_id}/', {'versao': 2, 'observacoes': ''}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_external_visit_is_idempotent_and_spaces_are_rejected(self):
        _, token = create_client(actor=self.admin, name='AgroHub visitas')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        data = self.data(id_externo='visita-1', requerente_id='externo-1', requerente='Visitante')
        url = '/api/v1/integracoes/agendamentos/'
        response = api.post(url, data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(api.post(url, data, format='json').status_code, 200)
        denied = api.post(url, {**data, 'id_externo': 'sala-1', 'categoria': 'espaco',
                               'objeto': 42, 'motivo': 'Sala'}, format='json')
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_external_legacy_space_replay_returns_original_without_new_reservation(self):
        client, token = create_client(actor=self.admin, name='Legado AgroHub')
        booking = Agendamento.objects.create(espaco_legado_id=42, espaco_legado_nome='Sala antiga', motivo='Antigo', inicio=self.start, fim=self.end)
        canonical = {'categoria': 'espaco', 'objeto': 42, 'motivo': 'Antigo',
                     'id_externo': 'antigo-1', 'requerente_id': 'pessoa-1', 'requerente': 'Ana',
                     'inicio': '2026-11-01T17:00:00+00:00', 'fim': '2026-11-01T18:00:00+00:00'}
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                                          ensure_ascii=False).encode()).hexdigest()
        PedidoIntegracao.objects.create(cliente=client, id_externo='antigo-1', requerente_id='pessoa-1',
                                        conteudo_digest=digest, agendamento=booking)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        response = api.post('/api/v1/integracoes/agendamentos/', canonical, format='json')
        self.assertEqual((response.status_code, response.data['id'], response.data['repetido']),
                         (200, booking.pk, True))
        denied = api.post('/api/v1/integracoes/agendamentos/', {**canonical, 'id_externo': 'novo-1'}, format='json')
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(Agendamento.objects.count(), 1)
