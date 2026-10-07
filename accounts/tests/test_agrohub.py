from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from accounts.tests.agrohub_stub import AccountsStub, PASSWORD


class AgroHubAccountsTests(TestCase):
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
        self.stub.reset()

    def login(self, client=None, **extra):
        return (client or self.client).post('/entrar/', {'username': 'agro-ana', 'password': PASSWORD, **extra})

    def test_login_uses_authoritative_me_identity_with_staff_as_regular_internal_user(self):
        response = self.login()
        self.assertRedirects(response, '/index/')
        user = get_user_model().objects.get(agrohub_id=42)
        self.assertEqual((user.first_name, user.last_name, user.email), ('Ana', 'Silva', 'ana@example.test'))
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_superuser or user.is_staff or user.groups.exists())
        self.assertEqual(self.client.session['_auth_user_id'], str(user.pk))
        self.assertNotContains(self.client.get('/perfil/'), 'access-1')
        self.assertNotContains(self.client.get('/perfil/'), 'refresh-1')

    def test_matching_local_admin_username_or_email_does_not_merge_accounts(self):
        local = get_user_model().objects.create_superuser('agro-ana', email='ana@example.test', password=PASSWORD)
        self.login()
        remote = get_user_model().objects.get(agrohub_id=42)
        self.assertNotEqual(remote.pk, local.pk)
        self.assertFalse(remote.is_superuser)
        self.assertEqual(self.client.get('/usuarios/').status_code, 403)

    def test_local_password_does_not_authenticate_when_api_rejects(self):
        get_user_model().objects.create_superuser('local-admin', password=PASSWORD)
        response = self.client.post('/entrar/', {'username': 'local-admin', 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_registration_posts_documented_fields_and_logs_in_without_local_password(self):
        data = {'username': 'agro-ana', 'email': 'ana@example.test', 'password': PASSWORD,
                'password_confirm': PASSWORD, 'first_name': 'Ana', 'last_name': 'Silva', 'cpf': '', 'telefone': ''}
        response = self.client.post('/registro/', data)
        self.assertRedirects(response, '/index/')
        posted = next(row[2] for row in self.stub.state['requests'] if row[1].endswith('/register/'))
        self.assertEqual(posted, data)
        self.assertFalse(get_user_model().objects.get(agrohub_id=42).has_usable_password())

    def test_registration_rejects_password_mismatch_and_privilege_fields_without_api_write(self):
        data = {'username': 'nova', 'email': 'nova@example.test', 'password': PASSWORD,
                'password_confirm': 'Outra-senha-2026'}
        self.assertEqual(self.client.post('/registro/', data).status_code, 200)
        data.update(password_confirm=PASSWORD, is_superuser='true')
        self.assertEqual(self.client.post('/registro/', data).status_code, 200)
        self.assertFalse(self.stub.state['requests'])
        self.assertFalse(get_user_model().objects.exists())

    def test_profile_updates_only_api_mutable_fields_and_preserves_local_privileges(self):
        self.login()
        user = get_user_model().objects.get(agrohub_id=42)
        user.groups.add(Group.objects.get(name='Administradores'))
        response = self.client.post('/perfil/', {'first_name': 'Beatriz', 'last_name': 'Souza',
                                                'cpf': '52998224725', 'telefone': '64999990000'})
        self.assertRedirects(response, '/perfil/')
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Beatriz')
        self.assertTrue(user.groups.filter(name='Administradores').exists())
        writes = [row for row in self.stub.state['requests'] if row[0] == 'PATCH']
        self.assertEqual(writes[0][2], {'first_name': 'Beatriz', 'last_name': 'Souza',
                                      'cpf': '52998224725', 'telefone': '64999990000'})
        self.assertEqual(writes[0][3], 'Bearer access-1')

    def test_profile_rejects_username_email_and_administrative_changes(self):
        self.login()
        for field in ('username', 'email', 'is_staff', 'is_superuser', 'agrohub_id', 'profile'):
            response = self.client.post('/perfil/', {'first_name': 'Outra', field: 'alterado'})
            self.assertEqual(response.status_code, 200)
        self.assertFalse(any(row[0] == 'PATCH' for row in self.stub.state['requests']))

    def test_photo_upload_is_multipart_and_avatar_uses_remote_picture(self):
        self.login()
        image = BytesIO()
        Image.new('RGB', (30, 30), 'blue').save(image, 'PNG')
        response = self.client.post('/perfil/foto/', {'foto': SimpleUploadedFile('perfil.png', image.getvalue(), 'image/png')})
        self.assertRedirects(response, '/perfil/')
        upload = next(row for row in self.stub.state['requests'] if row[0] == 'PUT')
        self.assertEqual(set(upload[2]), {'profile_picture'})
        self.assertEqual(upload[2]['profile_picture']['content_type'], 'image/webp')
        user = get_user_model().objects.get(agrohub_id=42)
        picture = self.client.get(f'/usuarios/{user.pk}/foto/')
        self.assertEqual((picture.status_code, picture['Content-Type']), (200, 'image/webp'))
        media_request = next(row for row in self.stub.state['requests'] if row[1] == '/media/profile.png')
        self.assertIsNone(media_request[3])

    def test_expired_access_refreshes_and_revoked_refresh_ends_session(self):
        self.login()
        self.stub.state['expired'] = True
        self.assertEqual(self.client.get('/index/').status_code, 200)
        self.assertTrue(any(row[1].endswith('/login/refresh/') for row in self.stub.state['requests']))
        self.stub.state.update(expired=True, reject_refresh=True)
        self.assertEqual(self.client.get('/index/').status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_refresh_cannot_switch_identity(self):
        self.login()
        self.stub.state['expired'] = True
        self.stub.state['profile']['id'] = 77
        self.assertEqual(self.client.get('/index/').status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(get_user_model().objects.filter(agrohub_id=77).exists())

    def test_reset_request_and_confirmation_send_documented_fields(self):
        response = self.client.post('/recuperar-senha/', {'email': 'ana@example.test'})
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/recuperar-senha/confirmar/', {'uid': 'NDI', 'token': 'test-reset-token',
            'new_password': PASSWORD, 'new_password_confirm': PASSWORD})
        self.assertRedirects(response, '/entrar/')
        writes = [row for row in self.stub.state['requests'] if row[0] == 'POST']
        self.assertEqual(writes[0][2], {'email': 'ana@example.test'})
        self.assertEqual(writes[1][2], {'uid': 'NDI', 'token': 'test-reset-token',
                                     'new_password': PASSWORD, 'new_password_confirm': PASSWORD})

    def test_reset_link_removes_token_from_url_and_avoids_cache_and_referrer(self):
        response = self.client.get('/recuperar-senha/confirmar/?uid=NDI&token=test-reset-token')
        self.assertRedirects(response, '/recuperar-senha/confirmar/')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertIn('no-store', response['Cache-Control'])
        clean_page = self.client.get(response.url)
        self.assertEqual(clean_page['Referrer-Policy'], 'same-origin')
        self.assertNotContains(clean_page, 'test-reset-token')

    def test_provider_failure_and_malformed_tokens_never_authenticate(self):
        for payload in [(503, {'detail': 'internal access secret'}), (200, {'access': '', 'refresh': 'refresh-1'})]:
            self.stub.state['responses'][('POST', '/api/v1/accounts/login/')] = payload
            response = self.login()
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)
            self.assertNotContains(response, 'internal access secret')
        self.assertFalse(get_user_model().objects.exists())

    def test_only_remote_login_in_admin_and_csrf_is_required_for_all_writes(self):
        local = get_user_model().objects.create_superuser('local-admin', password=PASSWORD)
        response = self.client.post('/admin/login/?next=/admin/', {'username': local.username, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        strict = Client(enforce_csrf_checks=True)
        for path in ('/entrar/', '/registro/', '/recuperar-senha/', '/recuperar-senha/confirmar/'):
            self.assertEqual(strict.post(path, {'email': 'ana@example.test'}).status_code, 403)

    def test_logout_removes_provider_tokens(self):
        self.login()
        self.client.post('/sair/')
        self.assertFalse(any('agrohub' in key for key in self.client.session.keys()))

    def test_authenticated_registration_goes_to_dashboard(self):
        self.login()
        self.assertRedirects(self.client.get('/registro/'), '/index/')

    def test_admin_account_switch_keeps_credentials_for_new_identity(self):
        self.login()
        admin = get_user_model().objects.create_superuser('technical', agrohub_id=77, password=PASSWORD)
        old_profile = dict(self.stub.state['profile'])
        self.stub.state['profile'].update(id=77, username='technical', roles=['admin'])
        self.stub.state['login_tokens'] = ('access-77', 'refresh-77')
        self.stub.state['profiles_by_access'] = {'access-1': old_profile, 'access-77': dict(self.stub.state['profile'])}
        response = self.client.post('/admin/login/?next=/admin/', {'username': 'technical', 'password': PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(admin.pk))
        self.assertEqual(self.client.session['agrohub_credentials']['user_id'], 77)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_reset_link_in_revoked_session_never_enters_login_next(self):
        self.login()
        self.stub.state.update(expired=True, reject_refresh=True)
        response = self.client.get('/recuperar-senha/confirmar/?uid=NDI&token=secret-reset-token')
        self.assertRedirects(response, '/recuperar-senha/confirmar/')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertNotContains(self.client.get(response.url), 'secret-reset-token')
        confirmed = self.client.post(response.url, {'new_password': PASSWORD, 'new_password_confirm': PASSWORD})
        self.assertRedirects(confirmed, '/entrar/', fetch_redirect_response=False)
        self.assertContains(self.client.get('/entrar/'), 'Senha atualizada. Entre com a nova senha do AgroHub.')
        payload = self.stub.state['requests'][-1][2]
        self.assertEqual(payload['token'], 'secret-reset-token')

    def test_remote_photo_does_not_accept_arbitrary_origin(self):
        self.stub.state['profile']['profile'] = {'profile_picture': 'https://outside.example/private.png'}
        self.login()
        user = get_user_model().objects.get(agrohub_id=42)
        self.assertEqual(user.agrohub_foto_url, '')
        self.assertEqual(self.client.get(f'/usuarios/{user.pk}/foto/').status_code, 404)

    def test_remote_account_deactivation_ends_session(self):
        self.login()
        self.stub.state['profile']['is_active'] = False
        self.assertEqual(self.client.get('/index/').status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_provider_outage_blocks_private_page_without_destroying_session(self):
        self.login()
        self.stub.state['responses'][('GET', '/api/v1/accounts/me/')] = (503, {'detail': 'private debug'})
        response = self.client.get('/index/')
        self.assertEqual(response.status_code, 503)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertNotContains(response, 'private debug', status_code=503)

    def test_invalid_reset_token_keeps_form_and_never_reports_success(self):
        self.stub.state['responses'][('POST', '/api/v1/accounts/password-reset/confirm/')] = (400, {'token': ['Token inválido.']})
        response = self.client.post('/recuperar-senha/confirmar/', {'uid': 'NDI', 'token': 'inválido',
            'new_password': PASSWORD, 'new_password_confirm': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.context['form'].errors)

    def test_malformed_picture_url_is_discarded_without_breaking_login(self):
        self.stub.state['profile']['profile'] = {'profile_picture': 'https://[broken/avatar.png'}
        self.assertRedirects(self.login(), '/index/')
        self.assertEqual(get_user_model().objects.get(agrohub_id=42).agrohub_foto_url, '')

    def test_connection_refused_shows_retry_without_local_fallback(self):
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        with override_settings(AGROHUB_API_BASE_URL=f'http://127.0.0.1:{port}/api/v1/'):
            response = self.login()
        self.assertContains(response, 'Tente entrar novamente')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_oversized_response_and_redirect_are_not_accepted(self):
        for payload in ((200, {'unexpected': 'x'*524289}),
                        (302, {}, {'Location': self.stub.origin+'/capture/'})):
            self.stub.state['responses'][('POST', '/api/v1/accounts/login/')] = payload
            response = self.login()
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(any(row[1] == '/capture/' for row in self.stub.state['requests']))

    def test_interrupted_error_body_and_chunked_response_are_normalized(self):
        from http.client import IncompleteRead
        from unittest.mock import patch, MagicMock
        from urllib.error import HTTPError
        from accounts.agrohub.client import AgroHubClient, AgroHubError
        error = HTTPError(self.stub.url, 400, 'Bad Request', {}, None)
        error.read = MagicMock(side_effect=TimeoutError)
        with patch('accounts.agrohub.client.build_opener') as opener:
            for failure in (error, IncompleteRead(b'partial')):
                opener.return_value.open.side_effect = failure
                with self.assertRaises(AgroHubError):
                    AgroHubClient().request('POST', 'login/', data={})

    def test_sessions_from_previous_local_backend_are_no_longer_accepted(self):
        local = get_user_model().objects.create_user('old-account', password=PASSWORD)
        self.client.force_login(local, backend='django.contrib.auth.backends.ModelBackend')
        self.assertRedirects(self.client.get('/index/'), '/entrar/?next=/index/', fetch_redirect_response=False)
