from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.agrohub.client import AgroHubError


class RegulationCalendarTests(TestCase):
    def test_both_pages_are_public_and_use_institutional_navigation(self):
        for path, title in (('/regimento/', 'Regimento'),
                            ('/calendario-de-funcionamento/', 'Segundo semestre/2026')):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, title)
                self.assertContains(response, 'class="institutional-header"')
                self.assertContains(response, '>Início</a>')
                self.assertNotContains(response, '>Home</a>')

    def test_home_links_to_the_local_pages(self):
        with patch('inovalab_app.conteudo.public_events.load_events', return_value=([], False)):
            response = self.client.get('/')
        self.assertContains(response, 'href="/regimento/"')
        self.assertContains(response, 'href="/calendario-de-funcionamento/"')
        self.assertNotContains(response, 'https://agrohub.unirv.edu.br/InovaLab/regimento/')

    def test_regulation_has_the_original_articles_and_hero(self):
        response = self.client.get('/regimento/')
        self.assertContains(response, 'Definição e princípios')
        self.assertContains(response, 'Art. 1º')
        self.assertContains(response, 'branding/inovalab/regulation-hero.png')
        self.assertGreater(len(response.context['regulation_sections']), 5)

    def test_calendar_has_six_months_and_only_the_source_holidays_and_recess(self):
        response = self.client.get('/calendario-de-funcionamento/')
        self.assertContains(response, 'branding/inovalab/calendar-hero.png')
        months = response.context['calendar_months']
        self.assertEqual([month['number'] for month in months], list(range(7, 13)))
        days = {cell['date'].isoformat(): cell for month in months for week in month['weeks']
                for cell in week if cell['is_current_month']}
        self.assertEqual(days['2026-10-12']['status'], 'feriado')
        self.assertEqual(days['2026-10-13']['status'], 'recesso')
        self.assertEqual(days['2026-10-18']['status'], 'recesso')
        self.assertEqual(days['2026-11-21']['status'], 'recesso')
        self.assertEqual(days['2026-10-07']['status'], '')
        self.assertEqual(days['2026-07-05']['status'], '')

    def test_remote_session_can_read_both_pages_during_api_outage(self):
        user = get_user_model().objects.create_user('leitor', agrohub_id=42)
        self.client.force_login(user)
        with patch('accounts.agrohub.client.AgroHubClient._read', side_effect=AgroHubError()) as transport:
            for path in ('/regimento/', '/calendario-de-funcionamento/'):
                self.assertEqual(self.client.get(path).status_code, 200)
            transport.assert_not_called()
