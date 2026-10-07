from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.tests.agrohub_stub import PASSWORD
from agenda.models import AgendaEquipamento, AgendaServico, EventoAgendamento
from agenda.tests.test_agrohub import VisitsProviderMixin, visit_fixture
from catalogo.models import Equipamento, Servico


class PersonalLocalBookingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('usuario-pessoal')
        cls.other = get_user_model().objects.create_user('outro-pessoal')
        cls.admin = get_user_model().objects.create_superuser('admin-pessoal')
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Máquina pessoal')

    def booking(self, actor, *, equipment=False, status='pendente', cancelled=False, reason='Pedido próprio'):
        start = datetime.fromisoformat('2099-11-01T10:00:00-03:00')
        data = {'criado_por': actor, 'inicio': start, 'fim': start + timedelta(hours=1),
                'motivo': reason, 'observacoes': 'Observações próprias', 'situacao': status,
                'cancelado_em': start if cancelled else None}
        return (AgendaEquipamento.objects.create(equipamento=self.equipment, **data) if equipment else
                AgendaServico.objects.create(servico=self.service, material_proprio=True, **data))

    def test_any_active_user_can_list_only_own_services_and_equipment_and_read_details(self):
        own = [self.booking(self.user), self.booking(self.user, equipment=True)]
        self.booking(self.other, reason='Pedido alheio')
        self.client.force_login(self.user)
        response = self.client.get('/agenda/meus/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['paginator'].count, 2)
        self.assertNotContains(response, 'Pedido alheio')
        self.assertNotContains(response, 'id="sidebar"')
        for booking in own:
            detail = self.client.get(f'/agenda/meus/{booking.categoria}/{booking.pk}/')
            self.assertContains(detail, 'Pedido próprio')
            self.assertContains(detail, booking.objeto_nome)
            self.assertContains(detail, 'Observações próprias')
            self.assertNotContains(detail, 'Editar agendamento')
        self.assertEqual(self.client.get('/agenda/').status_code, 403)
        self.assertEqual(self.client.get('/agenda/novo/').status_code, 403)

    def test_admin_personal_list_and_details_do_not_include_other_owners(self):
        own = self.booking(self.admin)
        other = self.booking(self.other)
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/meus/')
        self.assertEqual([row.pk for row in response.context['object_list']], [own.pk])
        self.assertEqual(self.client.get(f'/agenda/meus/servico/{other.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/agenda/servico/{other.pk}/').status_code, 200)

    def test_cancelled_and_rejected_records_remain_visible_with_details_and_history(self):
        cancelled = self.booking(self.user, cancelled=True, status='confirmado')
        rejected = self.booking(self.user, equipment=True, status='rejeitado')
        EventoAgendamento.objects.create(agenda_servico=cancelled, ator=self.user,
                                        ator_nome='usuario-pessoal', acao='cancelar', alteracoes={})
        self.client.force_login(self.user)
        for status, booking, label in (('cancelado', cancelled, 'Cancelado'), ('rejeitado', rejected, 'Recusado')):
            response = self.client.get('/agenda/meus/', {'situacao': status})
            self.assertEqual([row.categoria for row in response.context['object_list']], [booking.categoria])
            self.assertContains(response, label)
            detail = self.client.get(f'/agenda/meus/{booking.categoria}/{booking.pk}/')
            self.assertContains(detail, label)
        self.assertContains(self.client.get(f'/agenda/meus/servico/{cancelled.pk}/'), 'Histórico')

    def test_foreign_details_anonymous_and_inactive_users_and_mutations_are_denied(self):
        foreign = self.booking(self.other)
        own = self.booking(self.user)
        self.assertEqual(self.client.get('/agenda/meus/').status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/agenda/meus/servico/{foreign.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/agenda/meus/visita/{own.pk}/').status_code, 404)
        for url in ('/agenda/meus/', f'/agenda/meus/servico/{own.pk}/', '/agenda/visitas/'):
            self.assertEqual(self.client.post(url, {}).status_code, 405)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertNotEqual(self.client.get('/agenda/meus/').status_code, 200)

    def test_search_month_category_status_and_pagination_stay_with_own_records(self):
        for _ in range(27):
            self.booking(self.user, reason='Pedido filtrado')
        self.booking(self.other, reason='Pedido filtrado')
        self.booking(self.user, equipment=True, reason='Pedido filtrado')
        self.client.force_login(self.user)
        params = {'q': 'filtrado', 'mes': '2099-11', 'categoria': 'servico', 'situacao': 'pendente'}
        response = self.client.get('/agenda/meus/', params)
        self.assertEqual(response.context['paginator'].count, 27)
        self.assertEqual(len(response.context['object_list']), 25)
        for value in ('q=filtrado', 'mes=2099-11', 'categoria=servico', 'situacao=pendente', 'page=2'):
            self.assertContains(response, value)
        self.assertEqual(len(self.client.get('/agenda/meus/', {**params, 'page': 2}).context['object_list']), 2)
        for invalid in ({'mes': '2099-99'}, {'categoria': 'espaco'}, {'situacao': 'invalida'}):
            self.assertEqual(self.client.get('/agenda/meus/', invalid).status_code, 400)


class PersonalRemoteBookingsTests(VisitsProviderMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.stub.state['profile'].update(is_staff=False, roles=['student'])
        self.actor = get_user_model().objects.get(agrohub_id=42)

    def test_regular_account_sees_all_own_visit_statuses_and_local_bookings(self):
        self.stub.state['reservas'] = [visit_fixture(pk, status=status, owner_id=42)
            for pk, status in enumerate(('pendente', 'confirmada', 'cancelada', 'recusada'), 101)]
        self.stub.state['reservas'].append(visit_fixture(999, owner_id=99, titulo='Visita alheia'))
        AgendaServico.objects.create(servico=Servico.objects.first(), criado_por=self.actor,
            motivo='Serviço próprio', inicio=datetime.fromisoformat('2099-11-01T10:00:00-03:00'),
            fim=datetime.fromisoformat('2099-11-01T11:00:00-03:00'))
        response = self.client.get('/agenda/meus/')
        self.assertContains(response, 'Meus agendamentos')
        self.assertEqual(response.context['paginator'].count, 5)
        self.assertNotContains(response, 'Visita alheia')
        self.assertNotContains(response, 'id="sidebar"')
        for pk in range(101, 105):
            self.assertContains(response, f'/agenda/meus/visitas/{pk}/')
            self.assertContains(self.client.get(f'/agenda/meus/visitas/{pk}/'), 'Observação remota')
        self.assertEqual(self.client.get('/agenda/meus/visitas/999/').status_code, 404)
        self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 403)
        self.assertFalse(self.writes())

    def test_staff_provider_cannot_leak_other_users_visits_even_to_a_local_admin(self):
        self.stub.state['profile'].update(is_staff=True, roles=['admin'])
        self.stub.state['reservas'] = [visit_fixture(owner_id=99, titulo='Segredo de outro usuário')]
        with patch('agenda.personal.reservations') as listing, patch('agenda.personal.get_reservation') as detail:
            response = self.client.get('/agenda/meus/')
            self.assertContains(response, 'consulta individual')
            self.assertNotContains(response, 'Segredo de outro usuário')
            self.assertEqual(self.client.get('/agenda/meus/visitas/101/').status_code, 404)
        listing.assert_not_called()
        detail.assert_not_called()

    def test_provider_failure_keeps_local_records_without_writes(self):
        AgendaServico.objects.create(servico=Servico.objects.first(), criado_por=self.actor,
            motivo='Serviço preservado', inicio=datetime.fromisoformat('2099-11-01T10:00:00-03:00'),
            fim=datetime.fromisoformat('2099-11-01T11:00:00-03:00'))
        self.stub.state['responses'][('GET', '/api/v1/agendamentos/reservas/?sala=laboratorio-inovalab&page=1&page_size=100')] = (503, {})
        response = self.client.get('/agenda/meus/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Não foi possível consultar suas visitas')
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertFalse(self.writes())

    def test_personal_entry_is_discoverable_without_granting_internal_access(self):
        self.enterContext(patch('conteudo.public_events.load_events', return_value=([], False)))
        for path in ('/', '/perfil/'):
            self.assertContains(self.client.get(path), '/agenda/meus/')
        self.assertEqual(self.client.get('/agenda/novo/').status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get('/agenda/meus/'), '/entrar/?next=%2Fagenda%2Fmeus%2F',
                             fetch_redirect_response=False)
        response = self.client.post('/entrar/', {'username': 'agro-ana', 'password': PASSWORD,
                                                'next': '/agenda/meus/'})
        self.assertRedirects(response, '/agenda/meus/', fetch_redirect_response=False)
