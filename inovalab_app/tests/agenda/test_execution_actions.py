from datetime import date, time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase

from inovalab_app.agenda.models import AgendaVisita


class ExecutionActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('acao-realizacao-admin')
        cls.owner = get_user_model().objects.create_user('acao-realizacao-titular')

    def setUp(self):
        self.visit = AgendaVisita.objects.create(quantidade_pessoas=2, data=date(2026, 10, 8),
            hora_inicio=time(9), hora_termino=time(10), criado_por=self.owner)
        self.url = f'/agenda/visita/{self.visit.pk}/realizar/'
        self.enterContext(patch('django.utils.timezone.now', return_value=self.visit.inicio))
        self.client.force_login(self.admin)

    def test_post_requires_admin_csrf_and_version(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        self.assertEqual(secure.post(self.url, {'versao': 1}).status_code, 403)
        secure.get(self.visit.get_absolute_url())
        response = secure.post(self.url, {'versao': 1}, HTTP_X_CSRFTOKEN=secure.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.visit.get_absolute_url())
        self.assertEqual(self.client.post(self.url, {'versao': 1}).status_code, 409)
        self.assertEqual(self.visit.eventos.filter(acao='realizar').count(), 1)

    def test_owner_and_staff_cannot_realize(self):
        for actor in (self.owner, get_user_model().objects.create_user('acao-equipe', is_staff=True)):
            self.client.force_login(actor)
            self.assertEqual(self.client.post(self.url, {'versao': 1}).status_code, 403)
        self.assertFalse(self.visit.eventos.exists())

    def test_safe_return_preserves_filters_and_recovers_page(self):
        from inovalab_app.agenda.execution_views import safe_realization_return
        request = RequestFactory().post(self.url)
        request.user = self.admin
        for unsafe in ('https://evil.example/agenda/solicitacoes/', '//evil.example/agenda/solicitacoes/', '/usuarios/',
                       '/agenda/solicitacoes/?status=inventado', '/agenda/solicitacoes/?mes=invalido', 'http://['):
            self.assertEqual(safe_realization_return(request, unsafe, self.visit), self.visit.get_absolute_url())
        safe = safe_realization_return(request,
            '/agenda/solicitacoes/?status=confirmada&q=Visita&mes=2026-10&page=99', self.visit)
        parts = urlsplit(safe)
        self.assertEqual(parts.path, '/agenda/solicitacoes/')
        self.assertEqual(parse_qs(parts.query), {'status': ['confirmada'], 'q': ['Visita'], 'mes': ['2026-10'], 'page': ['1']})
        response = self.client.post(self.url, {'versao': 1, 'retorno': safe})
        self.assertEqual(response.url, safe)

    def test_form_rejects_extra_fields_and_before_start(self):
        self.assertEqual(self.client.post(self.url, {'versao': 1, 'situacao': 'confirmado'}).status_code, 400)
        with patch('django.utils.timezone.now', return_value=self.visit.inicio.replace(hour=8)):
            self.assertEqual(self.client.post(self.url, {'versao': 1}).status_code, 400)
        self.assertFalse(self.visit.eventos.exists())
