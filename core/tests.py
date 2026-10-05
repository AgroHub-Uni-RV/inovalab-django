from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from agenda.models import Agendamento
from catalogo.models import Servico
from tarefas.models import Tarefa
from core.dashboard import dashboard_context

NOW = datetime(2026, 12, 30, 15, tzinfo=dt_timezone.utc)


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser('painel-admin')
        cls.user = User.objects.create_user('painel-interno', first_name='Ana', last_name='Silva')
        cls.staff = User.objects.create_user('painel-staff', is_staff=True)
        cls.service = Servico.objects.create(nome='Serviço real')

    def task(self, responsible=None, status='demanda', **kwargs):
        return Tarefa.objects.create(servico=self.service, descricao='Descrição real',
            responsavel=responsible or self.user, status=status,
            inicio=NOW-timedelta(days=1) if status != 'demanda' else None,
            conclusao=NOW if status == 'concluido' else None, **kwargs)

    def booking(self, start=None, end=None, **kwargs):
        return Agendamento.objects.create(servico=self.service, requerente='Reserva confidencial', motivo='Motivo',
            inicio=start or NOW, fim=end or NOW+timedelta(hours=1), criado_por=self.admin, **kwargs)

    def panel(self, path='/painel/', user=None):
        self.client.force_login(user or self.admin)
        with patch('core.views.dashboard_context', side_effect=lambda actor, **filters: dashboard_context(actor, now=NOW, **filters)):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response

    def test_anonymous_and_inactive_redirect(self):
        self.assertEqual(self.client.get('/painel/').status_code, 302)
        self.client.force_login(self.user)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/painel/').status_code, 302)

    def test_common_and_staff_never_see_private_tasks_or_booking_days(self):
        own = self.task()
        self.task(self.admin)
        self.booking()
        for user in (self.user, self.staff):
            response = self.panel('/painel/?agenda=concluidos&tarefas=pendentes', user)
            self.assertEqual([t.pk for t in response.context['tasks']], [own.pk] if user == self.user else [])
            self.assertEqual(response.context['bookings'], [])
            self.assertFalse(any(day['reservations'] for month in response.context['months']
                                 for week in month['weeks'] for day in week))
            self.assertNotContains(response, 'Reserva confidencial')
            self.assertNotContains(response, '/agenda/')
            self.assertNotContains(response, '/banners/')
            self.assertNotContains(response, '/admin/accounts/user/')

    def test_business_admin_without_staff_sees_authorized_data_and_creation(self):
        self.user.groups.add(Group.objects.get(name='Administradores'))
        task = self.task(self.admin)
        booking = self.booking()
        response = self.panel(user=self.user)
        self.assertEqual([t.pk for t in response.context['tasks']], [task.pk])
        self.assertEqual([b.pk for b in response.context['bookings']], [booking.pk])
        self.assertContains(response, '/tarefas/nova/')
        self.assertContains(response, '/agenda/novo/')
        self.assertNotContains(response, '/admin/accounts/user/')

    def test_task_tabs_are_real_status_filters(self):
        tasks = {state: self.task(status=state) for state in ('demanda', 'criacao', 'avaliacao', 'concluido')}
        self.task(excluida_em=NOW)
        for tab, states in [('pendentes', ['demanda']), ('andamento', ['criacao', 'avaliacao']), ('concluidas', ['concluido'])]:
            response = self.panel('/painel/?tarefas='+tab)
            self.assertEqual({t.pk for t in response.context['tasks']}, {tasks[s].pk for s in states})

    def test_invalid_filters_are_normalized(self):
        task = self.task()
        response = self.panel('/painel/?tarefas=admin&agenda=privado')
        self.assertEqual(response.context['task_tab'], 'pendentes')
        self.assertEqual(response.context['booking_tab'], 'semana')
        self.assertEqual([t.pk for t in response.context['tasks']], [task.pk])

    def test_booking_tabs_use_exact_week_and_finished_boundaries(self):
        past = self.booking(NOW-timedelta(hours=1), NOW)
        week = self.booking()
        next_week = datetime(2027, 1, 4, 3, tzinfo=dt_timezone.utc)
        upcoming = self.booking(next_week, next_week+timedelta(hours=1))
        self.booking(cancelado_em=NOW)
        for tab, ids in [('semana', {week.pk}), ('proximos', {upcoming.pk}), ('concluidos', {past.pk})]:
            response = self.panel('/painel/?agenda='+tab)
            self.assertEqual({b.pk for b in response.context['bookings']}, ids)

    def test_calendar_six_months_cross_year_sunday_first(self):
        response = self.panel()
        months = response.context['months']
        self.assertEqual([(m['year'], m['month']) for m in months],
                         [(2026, 12), (2027, 1), (2027, 2), (2027, 3), (2027, 4), (2027, 5)])
        self.assertEqual(months[0]['weeks'][0][0]['date'].weekday(), 6)
        today = [d for w in months[0]['weeks'] for d in w if d['today']]
        self.assertEqual([d['date'].isoformat() for d in today], ['2026-12-30'])

    def test_midnight_end_and_cancelled_do_not_color_next_day(self):
        self.booking(datetime(2026, 12, 30, 22, tzinfo=dt_timezone.utc),
                     datetime(2026, 12, 31, 3, tzinfo=dt_timezone.utc))
        self.booking(datetime(2026, 12, 31, 12, tzinfo=dt_timezone.utc),
                     datetime(2026, 12, 31, 13, tzinfo=dt_timezone.utc), cancelado_em=NOW)
        response = self.panel()
        days = {d['date'].isoformat(): d for w in response.context['months'][0]['weeks'] for d in w if d['in_month']}
        self.assertEqual(days['2026-12-30']['reservations'], 1)
        self.assertEqual(days['2026-12-31']['reservations'], 0)

    def test_panels_limit_ten_but_offer_full_lists(self):
        for _ in range(12):
            self.task()
            self.booking()
        response = self.panel()
        self.assertEqual(len(response.context['tasks']), 10)
        self.assertEqual(len(response.context['bookings']), 10)
        self.assertContains(response, '/tarefas/')
        self.assertContains(response, '/agenda/')

    def test_empty_panels_and_long_html_names_are_safe(self):
        response = self.panel()
        self.assertContains(response, 'Nenhuma tarefa')
        self.assertContains(response, 'Nenhum agendamento')
        self.user.first_name = '<script>alert(1)</script>'
        self.user.save(update_fields=['first_name'])
        response = self.panel(user=self.user)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_private_no_store_and_read_only_panel(self):
        response = self.panel()
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.post('/painel/', {}).status_code, 405)

    def test_account_link_and_logout_are_real_csrf_forms(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/'), '/painel/')
        response = self.panel()
        self.assertContains(response, 'action="/sair/" method="post"')
        self.assertContains(response, '/admin/accounts/user/')
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        strict.get('/painel/')
        self.assertEqual(strict.post('/sair/').status_code, 403)
        self.assertEqual(strict.post('/sair/', {'csrfmiddlewaretoken': strict.cookies['csrftoken'].value}).status_code, 302)
