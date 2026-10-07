from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from agenda.models import AgendaEquipamento, AgendaServico, EventoAgendamento
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
        self.assertContains(self.client.get('/agenda/novo/'), 'Novo agendamento')

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
