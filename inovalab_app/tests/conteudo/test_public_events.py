from datetime import datetime, timezone
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.tests.agrohub_stub import AccountsStub


NOW = datetime(2026, 10, 6, 15, tzinfo=timezone.utc)
EVENT_ROUTE = '/api/v1/agrohub/eventos/?page=1&page_size=100'


def event(pk=9, **extra):
    return {'id': pk, 'title': 'Batalha de Robôs', 'summary': '',
            'description': 'Apresentação do projeto de robótica da UniRV.',
            'category': 'outro', 'is_active': True, 'image': '/media/eventos/robos.webp',
            'start_date': '2026-10-08T08:30:00-03:00', 'end_date': None,
            'location': 'Centro de Inovação', 'detail_url': '', **extra}


class PublicEventCalendarTests(TestCase):
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
        self.enterContext(patch('django.utils.timezone.now', return_value=NOW))

    def tearDown(self):
        cache.clear()

    def page(self, rows, status=200):
        self.stub.state['responses'][('GET', EVENT_ROUTE)] = (
            status, {'count': len(rows), 'results': rows, 'next': None})

    def test_root_renders_month_calendar_and_cards_from_the_public_api(self):
        self.page([event(), event(8, title='Revolução da Inteligência Artificial',
                                 start_date='2026-09-15T08:00:00-03:00',
                                 end_date='2026-09-16T12:00:00-03:00', category='workshop',
                                 summary='Duas manhãs de aprendizado.', detail_url='https://unieventos.unirv.edu.br/evento/71')])
        response = self.client.get('/')
        self.assertContains(response, 'inova-events-calendar__grid')
        self.assertContains(response, 'Outubro')
        self.assertContains(response, 'Batalha de Robôs')
        self.assertContains(response, 'Centro de Inovação')
        self.assertContains(response, 'Apresentação do projeto')
        self.assertContains(response, '8h30')
        self.assertContains(response, '8h às 16/09 12h')
        self.assertContains(response, 'WORKSHOP')
        self.assertContains(response, self.stub.origin+'/media/eventos/robos.webp')
        self.assertContains(response, 'https://unieventos.unirv.edu.br/evento/71')
        self.assertEqual([item['id'] for item in response.context['event_cards']], [9, 8])
        self.assertEqual(response.context['event_dates'], ['2026-09-15', '2026-10-08'])
        self.assertIsNone(self.stub.state['requests'][0][3])

    def test_api_failure_preserves_institutional_home_with_an_error_calendar(self):
        self.page([], status=503)
        response = self.client.get('/')
        self.assertContains(response, 'Ideias que')
        self.assertContains(response, 'inova-events-calendar__grid')
        self.assertContains(response, 'Não foi possível carregar os eventos do AgroHub.')
        self.assertNotContains(response, 'Nenhum evento publicado')

    def test_no_events_keeps_calendar_and_explicit_empty_state(self):
        self.page([])
        response = self.client.get('/')
        self.assertContains(response, 'inova-events-calendar__grid')
        self.assertContains(response, 'Nenhum evento publicado')

    def test_titles_are_escaped_and_unsafe_urls_are_not_links_or_images(self):
        self.page([event(title='<script>injetado</script>',
                         image='javascript:alert(1)', detail_url='javascript:alert(2)')])
        response = self.client.get('/')
        self.assertContains(response, '&lt;script&gt;injetado&lt;/script&gt;')
        self.assertNotContains(response, '<script>injetado</script>')
        self.assertNotContains(response, 'javascript:')

    def test_card_dates_use_brasilia_even_when_api_sends_utc(self):
        self.page([event(start_date='2026-10-08T02:30:00Z')])
        response = self.client.get('/')
        self.assertEqual(response.context['event_cards'][0]['date_iso'], '2026-10-07')
        self.assertEqual(response.context['event_cards'][0]['time_label'], '23h30')

    def test_detail_relative_url_resolves_against_agrohub(self):
        self.page([event(detail_url='/InovaLab/sobre/')])
        response = self.client.get('/')
        self.assertContains(response, self.stub.origin+'/InovaLab/sobre/')

    def test_unknown_category_uses_an_allowed_style(self):
        self.page([event(category='x" onclick="alert(1)')])
        response = self.client.get('/')
        self.assertEqual(response.context['event_cards'][0]['category'], 'outro')
        self.assertContains(response, 'OUTRO')

    def test_two_upcoming_events_do_not_include_old_events(self):
        self.page([event(), event(10, start_date='2026-10-09T08:00:00-03:00'),
                   event(8, start_date='2026-09-15T08:00:00-03:00')])
        response = self.client.get('/')
        self.assertEqual([card['id'] for card in response.context['event_cards']], [9, 10])
        self.assertNotIn('2026-09-15', response.context['event_dates'])

    def test_ongoing_and_today_events_remain_visible_after_their_start_time(self):
        self.page([event(1, start_date='2026-10-05T08:00:00-03:00',
                         end_date='2026-10-07T12:00:00-03:00'),
                   event(2, start_date='2026-10-06T08:00:00-03:00'),
                   event(3, start_date='2026-09-01T08:00:00-03:00')])
        response = self.client.get('/')
        self.assertEqual([card['id'] for card in response.context['event_cards']], [1, 2])

    def test_home_limits_cards_to_24_and_marks_later_pages_as_hidden(self):
        self.page([event(pk) for pk in range(1, 31)])
        response = self.client.get('/')
        self.assertEqual(len(response.context['event_cards']), 24)
        self.assertContains(response, 'data-event-card', count=24)
        self.assertContains(response, 'data-event-date="2026-10-08" hidden', count=22)
