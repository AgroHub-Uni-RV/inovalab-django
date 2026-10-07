import json
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from accounts.agrohub.client import AgroHubError
from inovalab_app.conteudo.models import Banner


@override_settings(AGROHUB_API_BASE_URL='https://agrohub.example/api/v1/')
class InstitutionalPagesTests(TestCase):
    def setUp(self):
        self.enterContext(patch('inovalab_app.conteudo.public_events.load_events', return_value=([], False)))

    def test_root_is_public_and_internal_area_redirects_to_new_login(self):
        response = self.client.get('/')
        self.assertContains(response, 'Ideias que')
        self.assertContains(response, 'viram soluções.')
        self.assertContains(self.client.get('/entrar/'), 'Entre na sua conta')
        self.assertRedirects(self.client.get('/index/'), '/entrar/?next=/index/',
                             fetch_redirect_response=False)

    def test_institutional_pages_have_navigation_and_ported_content(self):
        for path, text in [('/sobre/', 'Conheça o InovaLab'),
                           ('/servicos/', 'Serviços oferecidos'),
                           ('/contato/', 'Contato via formulário')]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, text)
                self.assertContains(response, 'href="/"')
                self.assertContains(response, 'href="/sobre/"')
                self.assertContains(response, 'href="/servicos/"')
                self.assertContains(response, 'href="/contato/"')
                self.assertNotContains(response, '>Home<')

    def test_authenticated_root_stays_public_with_internal_area_access(self):
        self.client.force_login(get_user_model().objects.create_user('visitante', is_staff=True))
        response = self.client.get('/')
        self.assertContains(response, 'Ideias que')
        self.assertContains(response, '/index/')
        self.assertNotContains(response, 'id="sidebar"')

    def test_public_pages_remain_available_with_remote_session_and_api_outage(self):
        user = get_user_model().objects.create_user('agro-visitante', agrohub_id=42)
        self.client.force_login(user)
        session = self.client.session
        session['agrohub_credentials'] = {'user_id': 42, 'access': 'fixture-access', 'refresh': 'fixture-refresh'}
        session.save()
        with patch('accounts.agrohub.client.AgroHubClient._read', side_effect=AgroHubError()) as transport:
            for path in ('/', '/sobre/', '/servicos/', '/contato/'):
                self.assertEqual(self.client.get(path).status_code, 200)
            transport.assert_not_called()

    def test_only_published_banner_for_each_page_replaces_the_default_hero(self):
        home = Banner.objects.create(titulo='Capa do início', banner_img='banners/home.webp', status='ativo')
        about = Banner.objects.create(titulo='Capa do sobre', banner_img='banners/about.webp', status='ativo', local='sobre')
        Banner.objects.create(titulo='Conteúdo privado', banner_img='banners/private.webp', status='inativo', ordem=0)
        for path, selected in [('/', home), ('/sobre/', about)]:
            response = self.client.get(path)
            self.assertContains(response, f'/banners/{selected.pk}/imagem/')
            self.assertContains(response, selected.titulo)
            self.assertNotContains(response, 'Conteúdo privado')


@override_settings(AGROHUB_API_BASE_URL='https://agrohub.example/api/v1/')
class ContactTests(TestCase):
    data = {'nome': '  Ana   Silva ', 'email': 'ANA@example.com', 'telefone': '(64) 99999-9999',
            'mensagem': 'Gostaria de conhecer o laboratório.', 'consent': 'on'}

    def test_valid_contact_posts_to_api_without_credentials_and_redirects(self):
        requests = []

        def transport(request, **kwargs):
            requests.append(request)
            return b'{"id": 10, "detail": "Mensagem recebida."}'

        with patch('accounts.agrohub.client.AgroHubClient._read', side_effect=transport):
            response = self.client.post('/contato/', {**self.data, 'site_code': 'agrohub'})
        self.assertRedirects(response, '/contato/', fetch_redirect_response=False)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(urlsplit(request.full_url).path, '/api/v1/contact/')
        self.assertEqual(request.method, 'POST')
        self.assertIsNone(request.get_header('Authorization'))
        payload = json.loads(request.data)
        self.assertEqual(payload['site_code'], 'inovalab')
        self.assertEqual(payload['nome'], 'Ana Silva')
        self.assertEqual(payload['email'], 'ana@example.com')
        self.assertNotIn('consent', payload)
        self.assertNotIn('website', payload)
        self.assertContains(self.client.get('/contato/'), 'Mensagem recebida')

    def test_invalid_data_consent_and_honeypot_never_call_api(self):
        with patch('accounts.agrohub.client.AgroHubClient._read') as transport:
            for data in [{**self.data, 'email': 'inválido'}, {**self.data, 'consent': ''},
                         {**self.data, 'mensagem': 'oi'}, {**self.data, 'website': 'spam'}]:
                response = self.client.post('/contato/', data)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context['contact_form'].errors)
            transport.assert_not_called()

    def test_api_failure_preserves_message_and_does_not_report_success(self):
        with patch('accounts.agrohub.client.AgroHubClient._read', side_effect=AgroHubError()):
            response = self.client.post('/contato/', self.data)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, self.data['mensagem'], status_code=503)
        self.assertContains(response, 'Não foi possível confirmar', status_code=503)
        self.assertNotContains(response, 'Mensagem recebida com sucesso', status_code=503)

    def test_contact_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/contato/', self.data).status_code, 403)

    def test_get_contact_does_not_send_messages(self):
        with patch('accounts.agrohub.client.AgroHubClient._read') as transport:
            self.assertEqual(self.client.get('/contato/').status_code, 200)
            transport.assert_not_called()

    def test_consent_error_is_linked_to_the_checkbox(self):
        response = self.client.post('/contato/', {**self.data, 'consent': ''})
        self.assertContains(response, 'aria-describedby="id_consent_error"', status_code=400)

    def test_api_validation_errors_are_shown_without_losing_the_input(self):
        with patch('accounts.agrohub.client.AgroHubClient._read',
                   side_effect=AgroHubError(400, {'email': ['Confira este e-mail.']})):
            response = self.client.post('/contato/', self.data)
        self.assertContains(response, 'Confira este e-mail.', status_code=400)
        self.assertContains(response, self.data['mensagem'], status_code=400)

    def test_response_without_receipt_id_does_not_claim_success(self):
        with patch('accounts.agrohub.client.AgroHubClient._read', return_value=b'{"detail":"ok"}'):
            response = self.client.post('/contato/', self.data)
        self.assertContains(response, 'Não foi possível confirmar', status_code=503)
