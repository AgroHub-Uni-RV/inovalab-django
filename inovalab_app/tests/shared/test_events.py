from inovalab_app.tests.agenda.helpers import make_service, make_booking
from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.tests.agrohub_stub import AccountsStub
from inovalab_app.shared.dashboard import dashboard_context


NOW = datetime(2026, 10, 6, 15, tzinfo=timezone.utc)
FIRST_PAGE = '/api/v1/agrohub/eventos/?page=1&page_size=100'
SECOND_PAGE = '/api/v1/agrohub/eventos/?page=2&page_size=100'


def event(pk=1, title='Workshop AgroHub', start='2026-10-08T08:30:00-03:00', end=None, active=True):
    return {'id': pk, 'title': title, 'start_date': start, 'end_date': end, 'is_active': active}


class EcosystemCalendarTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stub = AccountsStub()
        cls.provider_settings = override_settings(AGROHUB_API_BASE_URL=cls.stub.url, DEBUG=True)
        cls.provider_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.provider_settings.disable()
        cls.stub.close()
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.stub.reset()
        self.user = get_user_model().objects.create_user('calendario', is_staff=True)
        self.client.force_login(self.user)
        self.enterContext(patch('inovalab_app.shared.views.dashboard_context', side_effect=lambda actor, **filters:
                              dashboard_context(actor, now=NOW, **filters)))

    def tearDown(self):
        cache.clear()

    def page(self, rows, next_page=None, *, path=FIRST_PAGE, status=200):
        self.stub.state['responses'][('GET', path)] = (status, {'count': len(rows), 'next': next_page, 'results': rows})

    def days(self, response):
        return {day['date'].isoformat(): day for month in response.context['months']
                for week in month['weeks'] for day in week if day['in_month']}

    def test_index_marks_real_event_date_with_escaped_title_and_no_bearer(self):
        self.page([event(title='<script>Workshop</script>')])
        response = self.client.get('/index/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.days(response)['2026-10-08'].get('events', []), ['<script>Workshop</script>'])
        self.assertContains(response, '&lt;script&gt;Workshop&lt;/script&gt;')
        self.assertNotContains(response, '<script>Workshop</script>')
        self.assertNotContains(response, 'day holiday')
        self.assertNotContains(response, 'day recess')
        request = next(row for row in self.stub.state['requests'] if row[1] == FIRST_PAGE)
        self.assertIsNone(request[3])

    def test_period_uses_sao_paulo_days_and_excludes_midnight_end(self):
        self.page([event(start='2026-10-08T02:30:00Z', end='2026-10-09T03:00:00Z'),
                   event(pk=2, start='2026-11-01T10:00:00-03:00')])
        days = self.days(self.client.get('/index/'))
        self.assertEqual(days['2026-10-07'].get('events', []), ['Workshop AgroHub'])
        self.assertEqual(days['2026-10-08'].get('events', []), ['Workshop AgroHub'])
        self.assertEqual(days['2026-10-09'].get('events', []), [])
        self.assertEqual(days['2026-11-01'].get('events', []), ['Workshop AgroHub'])
        self.assertEqual(days['2026-10-06'].get('events', []), [])

    def test_all_pages_are_loaded_at_fixed_origin_and_cached_without_duplicates(self):
        self.page([event()], 'https://outside.example/steal?access=secret')
        self.page([event(), event(pk=2, title='Pitch')], path=SECOND_PAGE)
        response = self.client.get('/index/')
        self.assertEqual(self.days(response)['2026-10-08'].get('events', []), ['Workshop AgroHub', 'Pitch'])
        self.client.get('/index/')
        self.assertEqual([row[1] for row in self.stub.state['requests']], [FIRST_PAGE, SECOND_PAGE])

    def test_inactive_invalid_and_out_of_period_events_do_not_mark_days(self):
        self.page([event(active=False), event(pk=2, start='invalid'),
                   event(pk=3, end='2026-10-07T08:00:00-03:00'),
                   event(pk=4, start='2026-09-01T12:00:00-03:00'),
                   event(pk=5, start='2027-04-01T12:00:00-03:00')])
        response = self.client.get('/index/')
        self.assertFalse(any(day.get('events') for day in self.days(response).values()))
        self.assertTrue(any(row[1] == FIRST_PAGE for row in self.stub.state['requests']))

    def test_provider_failure_keeps_dashboard_and_recovers_on_next_request(self):
        self.page([], status=503)
        response = self.client.get('/index/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Não foi possível carregar os eventos do AgroHub.')
        self.page([event()])
        self.assertEqual(self.days(self.client.get('/index/'))['2026-10-08'].get('events', []), ['Workshop AgroHub'])

    def test_bad_pagination_discards_partial_events_instead_of_claiming_complete(self):
        self.page([event()], self.stub.origin+SECOND_PAGE)
        self.stub.state['responses'][('GET', SECOND_PAGE)] = (200, {'results': 'invalid'})
        response = self.client.get('/index/')
        self.assertContains(response, 'Não foi possível carregar os eventos do AgroHub.')
        self.assertEqual(self.days(response)['2026-10-08'].get('events', []), [])

    def test_unending_pagination_is_bounded_and_does_not_show_partial_events(self):
        for page in range(1, 21):
            self.page([event(pk=page)], 'https://outside.example/next',
                      path=f'/api/v1/agrohub/eventos/?page={page}&page_size=100')
        response = self.client.get('/index/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Não foi possível carregar os eventos do AgroHub.')
        self.assertEqual(len(self.stub.state['requests']), 20)
        self.assertEqual(self.days(response)['2026-10-08'].get('events', []), [])

    def test_events_keep_authorized_reservation_count_and_neutral_today(self):
        from inovalab_app.agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico
        from inovalab_app.catalogo.models import Servico
        make_booking(actor=self.user, prazo=datetime(2026, 10, 8, 13, tzinfo=timezone.utc))
        self.page([event()])
        response = self.client.get('/index/')
        days = self.days(response)
        self.assertEqual(days['2026-10-08']['reservations'], 1)
        self.assertEqual(days['2026-10-08']['events'], ['Workshop AgroHub'])
        self.assertContains(response, 'class="day reserved event"')
        self.assertEqual(days['2026-10-06']['events'], [])
        self.assertContains(response, 'class="day today"')

    def agenda_days(self, response):
        return {day['date'].isoformat(): day for week in response.context['weeks']
                for day in week if day['in_month']}

    def test_agenda_and_dashboard_share_feed_cache_and_escape_event_titles(self):
        self.page([event(title='<script>Workshop</script>'), event(pk=2, title='Pitch'),
                   event(pk=3, active=False), event(pk=4, start='invalid')])
        dashboard = self.client.get('/index/')
        agenda = self.client.get('/agenda/', {'mes': '2026-10', 'q': 'sem reservas', 'categoria': 'visita'})
        self.assertEqual(self.agenda_days(agenda)['2026-10-08']['events'],
                         self.days(dashboard)['2026-10-08']['events'])
        self.assertEqual(self.agenda_days(agenda)['2026-10-08']['events'], ['<script>Workshop</script>', 'Pitch'])
        self.assertEqual(agenda.context['paginator'].count, 0)
        self.assertContains(agenda, '&lt;script&gt;Workshop&lt;/script&gt;')
        self.assertNotContains(agenda, '<script>Workshop</script>')
        requests = [row for row in self.stub.state['requests'] if row[1] == FIRST_PAGE]
        self.assertEqual(len(requests), 1)
        self.assertIsNone(requests[0][3])

    def test_agenda_events_cover_local_days_across_months_and_exclude_midnight_end(self):
        self.page([event(start='2026-09-30T02:30:00Z', end='2026-10-02T03:00:00Z'),
                   event(pk=2, title='Sem término', start='2026-10-31T23:30:00-03:00'),
                   event(pk=3, title='Instantâneo', start='2026-10-03T10:00:00-03:00',
                         end='2026-10-03T10:00:00-03:00')])
        october = self.agenda_days(self.client.get('/agenda/', {'mes': '2026-10'}))
        self.assertEqual(october['2026-10-01']['events'], ['Workshop AgroHub'])
        self.assertEqual(october['2026-10-02']['events'], [])
        self.assertEqual(october['2026-10-03']['events'], ['Instantâneo'])
        self.assertEqual(october['2026-10-31']['events'], ['Sem término'])
        september = self.agenda_days(self.client.get('/agenda/', {'mes': '2026-09'}))
        self.assertEqual(september['2026-09-29']['events'], ['Workshop AgroHub'])
        self.assertEqual(september['2026-09-30']['events'], ['Workshop AgroHub'])
        november = self.agenda_days(self.client.get('/agenda/', {'mes': '2026-11'}))
        self.assertFalse(any(day['events'] for day in november.values()))

    def test_agenda_keeps_today_reservations_and_external_events_independent(self):
        self.page([event(start='2026-10-06T08:30:00-03:00')])
        booking = make_booking(actor=self.user, prazo=NOW)
        with patch('django.utils.timezone.now', return_value=NOW):
            response = self.client.get('/agenda/', {'mes': '2026-10'})
        day = self.agenda_days(response)['2026-10-06']
        self.assertTrue(day['is_today'])
        self.assertEqual(day['events'], ['Workshop AgroHub'])
        self.assertEqual(day['count'], 1)
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertContains(response, booking.get_absolute_url())
        self.assertContains(response, 'aria-current="date"', count=1)
        self.assertContains(response, 'class="calendar-event"', count=1)

    def test_agenda_provider_failure_preserves_reservations_and_recovers(self):
        make_booking(actor=self.user, prazo=NOW)
        self.page([], status=503)
        failed = self.client.get('/agenda/', {'mes': '2026-10'})
        self.assertEqual(failed.status_code, 200)
        self.assertContains(failed, 'Não foi possível carregar os eventos do AgroHub.')
        self.assertEqual(self.agenda_days(failed)['2026-10-06']['count'], 1)
        self.assertFalse(any(day['events'] for day in self.agenda_days(failed).values()))
        self.page([event()])
        recovered = self.client.get('/agenda/', {'mes': '2026-10'})
        self.assertNotContains(recovered, 'Não foi possível carregar os eventos do AgroHub.')
        self.assertEqual(self.agenda_days(recovered)['2026-10-08']['events'], ['Workshop AgroHub'])
