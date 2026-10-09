from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from inovalab_app.agenda.models import AgendaVisita, AgendaEquipamento
from inovalab_app.agenda.services import mark_visit_realized
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.shared.dashboard import dashboard_context
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tests.agenda.helpers import make_booking
from inovalab_app.tests.agenda.test_execution import NOW


class ExecutionFrontendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('execucao-telas-admin')
        cls.owner = get_user_model().objects.create_user('execucao-telas-titular', is_staff=True)
        cls.external = get_user_model().objects.create_user('execucao-telas-externo')

    def setUp(self):
        self.enterContext(patch('django.utils.timezone.now', return_value=NOW))
        self.enterContext(patch('inovalab_app.shared.views.load_events', return_value=([], False)))

    def service(self, **fields):
        return make_booking(actor=self.owner, prazo=NOW-timedelta(hours=1), titulo='Serviço de execução', **fields)

    def task(self, booking, status='demanda', completed=NOW):
        return Tarefa.objects.create(agendamento_servico=booking, responsavel=self.owner,
            descricao='TAREFA CONFIDENCIAL', status=status, inicio=NOW-timedelta(hours=2),
            conclusao=completed if status == 'concluido' else None)

    def visit(self, **fields):
        return AgendaVisita.objects.create(criado_por=fields.pop('criado_por', self.owner),
            data=NOW.date(), hora_inicio=NOW.replace(hour=11).time(),
            hora_termino=NOW.replace(hour=13).time(), quantidade_pessoas=2, **fields)

    def test_same_state_labels_across_internal_and_personal_pages(self):
        booking = self.service()
        self.task(booking, 'concluido')
        self.client.force_login(self.owner)
        for path in ('/agenda/?mes=', booking.get_absolute_url(), '/agenda/meus/',
                     f'/agenda/meus/servico/{booking.pk}/', '/painel/?agenda=concluidos'):
            response = self.client.get(path)
            self.assertContains(response, 'Concluído com atraso')
            self.assertNotContains(response, 'TAREFA CONFIDENCIAL')
        response = self.client.get(booking.get_absolute_url())
        self.assertContains(response, 'Confirmado')

    def test_filters_preserve_calendar_and_clear_month_semantics(self):
        late = self.service()
        make_booking(actor=self.owner, prazo=NOW, situacao='pendente')
        foreign = make_booking(actor=self.admin, prazo=NOW-timedelta(hours=1))
        self.client.force_login(self.owner)
        for path in ('/agenda/', '/agenda/meus/'):
            response = self.client.get(path, {'execucao': 'atrasado', 'categoria': 'servico', 'mes': '2026-10', 'q': 'Serviço'})
            self.assertEqual([row.pk for row in response.context['object_list']], [late.pk])
            self.assertEqual(response.context['selected_execution'], 'atrasado')
            self.assertNotContains(response, foreign.get_absolute_url())
            self.assertEqual(self.client.get(path, {'execucao': 'inventado'}).status_code, 400)
        self.client.force_login(self.admin)
        clean = self.client.get('/agenda/?mes=')
        self.assertEqual(clean.context['month'], '')
        self.assertEqual(clean.context['calendar_month'], '2026-10')
        self.assertContains(clean, 'data-clear-filters href="/agenda/?mes="')

    def test_realization_action_is_admin_only_and_full_page_is_preserved(self):
        visit = self.visit()
        self.client.force_login(self.admin)
        response = self.client.get(visit.get_absolute_url())
        self.assertContains(response, 'sheet-layout')
        self.assertContains(response, 'sheet-detail-topbar')
        self.assertContains(response, 'Marcar como realizada')
        self.assertNotContains(response, 'visit-realize-modal')
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(visit.get_absolute_url()), 'Marcar como realizada')
        mark_visit_realized(actor=self.admin, booking_id=visit.pk, expected_version=1)
        self.admin.delete()
        for path in (visit.get_absolute_url(), f'/agenda/meus/visita/{visit.pk}/'):
            response = self.client.get(path)
            self.assertContains(response, 'Realizada em 08/10/2026 12:00')
            self.assertContains(response, 'execucao-telas-admin')
            self.assertContains(response, 'Concluído')
            self.assertNotContains(response, 'Marcar como realizada')

    def test_past_unrealized_visit_is_not_completed(self):
        visit = self.visit()
        context = dashboard_context(self.admin, now=visit.fim+timedelta(seconds=1), booking_tab='concluidos')
        self.assertNotIn(('visita', visit.pk), [(row.categoria, row.pk) for row in context['bookings']])
        mark_visit_realized(actor=self.admin, booking_id=visit.pk, expected_version=1)
        self.assertIn(visit.pk, [row.pk for row in dashboard_context(self.admin, now=NOW, booking_tab='concluidos')['bookings']])

    def test_service_completion_ignores_deadline_until_all_tasks_complete(self):
        overdue = self.service()
        self.task(overdue)
        early = make_booking(actor=self.owner, prazo=NOW+timedelta(days=1))
        self.task(early, 'concluido', NOW-timedelta(minutes=1))
        rows = dashboard_context(self.admin, now=NOW, booking_tab='concluidos')['bookings']
        self.assertEqual([row.pk for row in rows], [early.pk])
        self.task(early)
        self.assertEqual(dashboard_context(self.admin, now=NOW, booking_tab='concluidos')['bookings'], [])

    def test_historical_equipment_keeps_legacy_dashboard_behavior(self):
        booking = AgendaEquipamento.objects.create(equipamento=Equipamento.objects.create(nome='Legado'),
            inicio=NOW-timedelta(hours=2), fim=NOW, criado_por=self.owner)
        row = dashboard_context(self.admin, now=NOW, booking_tab='concluidos')['bookings'][0]
        self.assertEqual((row.categoria, row.pk, row.estado_execucao), ('equipamento', booking.pk, 'nao_aplicavel'))
