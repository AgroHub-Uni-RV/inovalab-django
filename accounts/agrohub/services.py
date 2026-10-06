from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from accounts.agrohub.client import AgroHubClient, AgroHubError, safe_picture_url
from accounts.models import User


SESSION_KEY = 'agrohub_credentials'


def tokens(payload):
    if any(not isinstance(payload.get(name), str) or not payload[name] or len(payload[name]) > 16384
           for name in ('access', 'refresh')):
        raise AgroHubError()
    return {name: payload[name] for name in ('access', 'refresh')}


def validate_profile(profile):
    if type(profile.get('id')) is not int or not 0 < profile['id'] <= 9223372036854775807:
        raise AgroHubError()
    if profile.get('is_active') is not True:
        raise AgroHubError(401)
    limits = {'username': 150, 'email': 254, 'first_name': 150, 'last_name': 150, 'cpf': 14, 'telefone': 20}
    for name, maximum in limits.items():
        value = profile.get(name, '')
        if not isinstance(value, str) or len(value) > maximum or (name == 'username' and not value):
            raise AgroHubError()
    return profile


def sync_profile(user, profile):
    validate_profile(profile)
    if user.agrohub_id != profile['id'] or not user.is_active:
        raise AgroHubError(401)
    values = {name: profile.get(name, '') for name in ('email', 'first_name', 'last_name', 'cpf', 'telefone')}
    values['agrohub_username'] = profile['username']
    nested = profile.get('profile')
    values['agrohub_foto_url'] = safe_picture_url(nested.get('profile_picture')) if isinstance(nested, dict) else ''
    changed = [name for name, value in values.items() if getattr(user, name) != value]
    for name in changed:
        setattr(user, name, values[name])
    if changed:
        # Não atualizar flags/grupos/senha por dados remotos ou cópia obsoleta do usuário.
        user.save(update_fields=changed)
    return user


def provision(profile):
    validate_profile(profile)
    user = User.objects.filter(agrohub_id=profile['id']).first()
    if user is None:
        username = profile['username']
        try:
            User._meta.get_field('username').run_validators(username)
        except ValidationError:
            username = f'agrohub_{profile["id"]}'
        for attempt in range(3):
            if User.objects.filter(username=username).exists():
                username = f'agrohub_{profile["id"]}_{uuid4().hex[:12]}'
            try:
                with transaction.atomic():
                    user = User(username=username, agrohub_id=profile['id'])
                    user.set_unusable_password()
                    user.save()
                break
            except IntegrityError:
                user = User.objects.filter(agrohub_id=profile['id']).first()
                if user is not None:
                    break
                username = f'agrohub_{profile["id"]}_{uuid4().hex[:12]}'
        if user is None or user.pk is None:
            raise AgroHubError()
    return sync_profile(user, profile)


def begin_session(request, payload):
    credential = tokens(payload)
    profile = AgroHubClient().request('GET', 'me/', access=credential['access'])
    user = provision(profile)
    # Django pode limpar a sessão ao trocar de conta; persistir após login().
    request.agrohub_login_credentials = {**credential, 'user_id': user.agrohub_id}
    return user


def authenticated_request(request, method, route, *, data=None, photo=None, namespace='accounts', params=None):
    credential = request.session.get(SESSION_KEY)
    if not isinstance(credential, dict) or credential.get('user_id') != request.user.agrohub_id:
        raise AgroHubError(401)
    if any(not isinstance(credential.get(name), str) or not credential[name] for name in ('access', 'refresh')):
        raise AgroHubError(401)
    client = AgroHubClient()
    try:
        return client.request(method, route, data=data, photo=photo, access=credential['access'], namespace=namespace, params=params)
    except AgroHubError as error:
        if error.status != 401:
            raise
    payload = client.request('POST', 'login/refresh/', data={'refresh': credential['refresh']})
    renewed = tokens({**payload, 'refresh': payload.get('refresh', credential['refresh'])})
    profile = client.request('GET', 'me/', access=renewed['access'])
    validate_profile(profile)
    if profile['id'] != request.user.agrohub_id:
        raise AgroHubError(401)
    request.session[SESSION_KEY] = {**renewed, 'user_id': profile['id']}
    if photo is not None:
        photo.seek(0)
    if namespace == 'accounts' and method == 'GET' and route == 'me/':
        return profile
    return client.request(method, route, data=data, photo=photo, access=renewed['access'], namespace=namespace, params=params)
