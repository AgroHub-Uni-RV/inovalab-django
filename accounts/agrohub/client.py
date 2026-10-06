import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class AgroHubError(Exception):
    def __init__(self, status=503, errors=None):
        self.status = status
        self.errors = errors or {}
        super().__init__('Não foi possível acessar o AgroHub. Tente novamente em instantes.'
                         if status >= 500 else 'Confira os dados informados e tente novamente.')


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise URLError('Redirecionamento não permitido.')


def base_url():
    value = settings.AGROHUB_API_BASE_URL.rstrip('/')+'/'
    parsed = urlsplit(value)
    local = settings.DEBUG and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or (parsed.scheme != 'https' and not (local and parsed.scheme == 'http'))):
        raise ImproperlyConfigured('AGROHUB_API_BASE_URL deve ser HTTPS; HTTP é permitido somente em loopback no desenvolvimento.')
    return value


def safe_picture_url(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        return ''
    try:
        value = urljoin(base_url(), value)
        parsed, origin = urlsplit(value), urlsplit(base_url())
    except ValueError:
        return ''
    if parsed.username or parsed.password or parsed.fragment:
        return ''
    if (parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc):
        return value
    if parsed.scheme == 'https' and parsed.netloc in settings.AGROHUB_PHOTO_ALLOWED_HOSTS:
        return value
    return ''


class AgroHubClient:
    ROUTES = {'login/', 'login/refresh/', 'register/', 'me/', 'me/picture/',
              'password-reset/', 'password-reset/confirm/'}

    def request(self, method, route, *, data=None, access=None, photo=None):
        if route not in self.ROUTES:
            raise ValueError('Rota Accounts desconhecida.')
        headers = {'Accept': 'application/json'}
        if access:
            headers['Authorization'] = 'Bearer '+access
        body = None
        if photo is not None:
            boundary = 'inovalab-'+uuid4().hex
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="profile_picture"; '
                    'filename="perfil.webp"\r\nContent-Type: image/webp\r\n\r\n').encode()
            body += photo.read()+f'\r\n--{boundary}--\r\n'.encode()
            headers['Content-Type'] = 'multipart/form-data; boundary='+boundary
        elif data is not None:
            body = json.dumps(data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = Request(urljoin(base_url(), 'accounts/'+route), data=body, headers=headers, method=method)
        raw = self._read(request, limit=512*1024)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AgroHubError() from None
        if not isinstance(result, dict):
            raise AgroHubError()
        return result

    def picture(self, url):
        safe = safe_picture_url(url)
        if not safe:
            raise AgroHubError(400)
        # Fotos nunca recebem Bearer; não transmitir credenciais para URLs de mídia.
        return self._read(Request(safe, headers={'Accept': 'image/png,image/jpeg,image/webp'}), limit=5*1024*1024)

    def events_page(self, page, *, timeout=5):
        # A listagem pública responde sem JWT: nunca compartilhar credenciais no cache.
        url = urljoin(base_url(), 'agrohub/eventos/')+'?'+urlencode({'page': page, 'page_size': 100})
        raw = self._read(Request(url, headers={'Accept': 'application/json'}), limit=512*1024, timeout=timeout)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AgroHubError() from None
        if not isinstance(payload, dict):
            raise AgroHubError()
        return payload

    def _read(self, request, *, limit, timeout=None):
        try:
            with build_opener(NoRedirects()).open(request, timeout=timeout if timeout is not None else settings.AGROHUB_API_TIMEOUT) as response:
                raw = response.read(limit+1)
                if len(raw) > limit:
                    raise AgroHubError()
                return raw
        except HTTPError as error:
            errors = {}
            if error.code in (400, 422):
                try:
                    raw = error.read(64*1024+1)
                    value = json.loads(raw) if len(raw) <= 64*1024 else {}
                    allowed = {'username', 'email', 'password', 'password_confirm', 'first_name', 'last_name',
                               'cpf', 'telefone', 'profile_picture', 'uid', 'token',
                               'new_password', 'new_password_confirm', 'non_field_errors'}
                    if isinstance(value, dict):
                        for name, messages in value.items():
                            if name in allowed:
                                messages = [messages] if isinstance(messages, str) else messages
                                if isinstance(messages, list):
                                    errors[name] = [message[:500] for message in messages[:5] if isinstance(message, str)]
                except (ValueError, UnicodeError, OSError, HTTPException):
                    pass
            error.close()
            raise AgroHubError(error.code, errors) from None
        except (URLError, TimeoutError, OSError, ValueError, HTTPException):
            raise AgroHubError() from None
