"""Servidor HTTP controlado de Accounts; não acessa usuários do AgroHub real."""
import json
from copy import deepcopy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from threading import Thread

from PIL import Image


PROFILE = {'id': 42, 'username': 'agro-ana', 'email': 'ana@example.test', 'first_name': 'Ana',
           'last_name': 'Silva', 'cpf': '', 'telefone': '', 'is_active': True,
           'roles': ['staff'], 'is_staff': True, 'is_superuser': True, 'profile': None}
PASSWORD = 'AgroHub-Teste-2026!'


class AccountsStub:
    def __init__(self):
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.dispatch()

            def do_POST(self):
                self.dispatch()

            def do_PATCH(self):
                self.dispatch()

            def do_PUT(self):
                self.dispatch()

            def dispatch(self):
                raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                kind = self.headers.get('Content-Type', '')
                data = json.loads(raw) if raw and kind.startswith('application/json') else {}
                if kind.startswith('multipart/form-data'):
                    message = BytesParser().parsebytes(('Content-Type: '+kind+'\r\n\r\n').encode()+raw)
                    data = {part.get_param('name', header='content-disposition'): {
                        'filename': part.get_filename(), 'content_type': part.get_content_type(),
                        'content': part.get_payload(decode=True),
                    } for part in message.get_payload()}
                state = stub.state
                state['requests'].append((self.command, self.path, data, self.headers.get('Authorization')))
                override = state['responses'].get((self.command, self.path))
                if override:
                    return self.reply(*override)
                dispatch_extra = getattr(stub, 'dispatch_extra', None)
                if dispatch_extra and dispatch_extra(self, data):
                    return
                if self.command == 'GET' and self.path.startswith('/api/v1/agrohub/eventos/?'):
                    return self.reply(200, {'count': 0, 'next': None, 'results': []})
                if self.path == '/media/profile.png':
                    out = BytesIO()
                    Image.new('RGB', (32, 32), '#27348b').save(out, 'PNG')
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.end_headers()
                    self.wfile.write(out.getvalue())
                    return
                route = self.path.removeprefix('/api/v1/accounts/')
                if route == 'login/' and self.command == 'POST':
                    if data.get('username') not in (state['profile']['username'], state['profile']['email']) or data.get('password') != state['password']:
                        return self.reply(401, {'detail': 'Credenciais inválidas.'})
                    access, refresh = state.get('login_tokens', ('access-1', 'refresh-1'))
                    return self.reply(200, {'access': access, 'refresh': refresh, 'user': {'id': 999}})
                if route == 'register/' and self.command == 'POST':
                    state['profile'].update({key: value for key, value in data.items() if key in PROFILE})
                    return self.reply(201, {'access': 'access-1', 'refresh': 'refresh-1'})
                if route == 'login/refresh/':
                    if state['reject_refresh']:
                        return self.reply(401, {'detail': 'Token inválido.'})
                    state['expired'] = False
                    return self.reply(200, {'access': 'access-2', 'refresh': 'refresh-2'})
                if route.startswith('me/'):
                    profiles = state.get('profiles_by_access', {})
                    access = self.headers.get('Authorization', '').removeprefix('Bearer ')
                    if state['expired'] or access not in ('access-1', 'access-2', *profiles):
                        return self.reply(401, {'detail': 'Token expirado.'})
                    if route == 'me/' and self.command == 'GET':
                        return self.reply(200, profiles.get(access, state['profile']))
                    if route == 'me/' and self.command == 'PATCH':
                        state['profile'].update(data)
                        return self.reply(200, data)
                    if route == 'me/picture/' and self.command == 'PUT':
                        url = stub.origin+'/media/profile.png'
                        state['profile']['profile'] = {'profile_picture': url}
                        return self.reply(200, {'profile_picture': url})
                if route in ('password-reset/', 'password-reset/confirm/') and self.command == 'POST':
                    return self.reply(200, {'detail': 'Solicitação processada.'})
                self.reply(404, {'detail': 'Não encontrado.'})

            def reply(self, status, data, headers=None):
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.url = self.origin+'/api/v1/'
        self.reset()
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def reset(self):
        self.state = {'profile': deepcopy(PROFILE), 'requests': [], 'responses': {},
                      'expired': False, 'reject_refresh': False, 'password': PASSWORD}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


class AccountsProviderMixin:
    """Faz os testes anteriores de navegação usarem autenticação remota HTTP."""
    @classmethod
    def setUpClass(cls):
        from django.test import override_settings
        super().setUpClass()
        cls.provider = AccountsStub()
        cls.provider_override = override_settings(AGROHUB_API_BASE_URL=cls.provider.url, DEBUG=True)
        cls.provider_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.provider_override.disable()
        cls.provider.close()
        super().tearDownClass()

    def setUp(self):
        from accounts.tests.test_identity import PASSWORD as navigation_password
        super().setUp()
        self.provider.reset()
        account = self.ana if hasattr(self, 'ana') else self.user
        account.agrohub_id = 42
        account.save(update_fields=['agrohub_id'])
        self.provider.state['password'] = navigation_password
        self.provider.state['profile'].update({
            'username': account.username, 'email': account.email,
            'first_name': account.first_name, 'last_name': account.last_name,
        })
        original_force_login = self.client.force_login

        def force_remote_session(user, backend=None):
            original_force_login(user, backend=backend)
            if user.agrohub_id == 42:
                self.provider.state['profile']['roles'] = ['admin'] if (
                    user.is_superuser or user.groups.filter(name='Administradores').exists()) else ['staff']
                session = self.client.session
                session['agrohub_credentials'] = {
                    'access': 'access-1', 'refresh': 'refresh-1', 'user_id': 42,
                }
                session.save()

        self.client.force_login = force_remote_session
