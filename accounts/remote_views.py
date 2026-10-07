from time import time

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from accounts.agrohub.client import AgroHubClient, AgroHubError
from accounts.agrohub.services import authenticated_request, begin_session, sync_profile
from accounts.policies import can_access_panel, is_business_admin
from accounts.remote_forms import (AgroHubPhotoForm, AgroHubProfileForm, PasswordResetConfirmForm,
                                   PasswordResetForm, RegisterForm)
from accounts.remote_forms import RedactedHiddenInput


def add_api_errors(form, error):
    added = False
    for name, errors in error.errors.items():
        name = 'foto' if name == 'profile_picture' else name
        if name in form.fields and errors:
            form.add_error(name, errors)
            added = True
        elif name == 'non_field_errors' and errors:
            form.add_error(None, errors)
            added = True
    if not added:
        form.add_error(None, 'A sessão do AgroHub expirou. Entre novamente.' if error.status in (401, 403)
                       else str(error))


def remote_profile(request, *, photo_form=None):
    user = request.user
    initial = {name: getattr(user, name) for name in ('first_name', 'last_name', 'cpf', 'telefone')}
    form = AgroHubProfileForm(request.POST if request.method == 'POST' and photo_form is None else None, initial=initial)
    if request.method == 'POST' and photo_form is None and form.is_valid():
        try:
            authenticated_request(request, 'PATCH', 'me/', data=form.cleaned_data)
            profile = authenticated_request(request, 'GET', 'me/')
            sync_profile(user, profile)
        except AgroHubError as error:
            add_api_errors(form, error)
        else:
            messages.success(request, 'Perfil atualizado com sucesso no AgroHub.')
            return redirect('accounts:home')
    return render(request, 'accounts/home.html', {'form': form, 'photo_form': photo_form or AgroHubPhotoForm(),
                                                'agrohub_account': True, 'is_business_admin': is_business_admin(user),
                                                'profile_base_template': 'inovalab_app/catalogo/base.html' if can_access_panel(user)
                                                                         else 'accounts/public_profile_base.html'})


@never_cache
@login_required
@require_http_methods(['POST'])
def update_photo(request):
    if request.user.agrohub_id is None:
        return redirect('accounts:home')
    form = AgroHubPhotoForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            authenticated_request(request, 'PUT', 'me/picture/', photo=form.cleaned_data['foto'])
            profile = authenticated_request(request, 'GET', 'me/')
            sync_profile(request.user, profile)
        except AgroHubError as error:
            add_api_errors(form, error)
        else:
            messages.success(request, 'Foto atualizada com sucesso no AgroHub.')
            return redirect('accounts:home')
    return remote_profile(request, photo_form=form)


@never_cache
@sensitive_post_parameters('password', 'password_confirm')
@require_http_methods(['GET', 'POST'])
def register(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard' if can_access_panel(request.user) else 'conteudo:inicio')
    form = RegisterForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            payload = AgroHubClient().request('POST', 'register/', data=form.cleaned_data)
            user = begin_session(request, payload)
        except AgroHubError as error:
            add_api_errors(form, error)
        else:
            login(request, user, backend='accounts.backends.AgroHubBackend')
            return redirect('core:dashboard' if can_access_panel(user) else 'conteudo:inicio')
    return render(request, 'accounts/remote_form.html', {'form': form, 'title': 'Criar conta',
                  'intro': 'Cadastre sua conta no AgroHub para acessar o InovaLab.', 'button': 'Criar conta'})


@never_cache
@require_http_methods(['GET', 'POST'])
def password_reset(request):
    form = PasswordResetForm(request.POST if request.method == 'POST' else None)
    sent = False
    if request.method == 'POST' and form.is_valid():
        try:
            AgroHubClient().request('POST', 'password-reset/', data=form.cleaned_data)
        except AgroHubError as error:
            add_api_errors(form, error)
        else:
            sent = True
            form = PasswordResetForm()
    return render(request, 'accounts/remote_form.html', {'form': form, 'title': 'Recuperar senha',
                  'intro': 'Informe o e-mail da sua conta no AgroHub.', 'button': 'Enviar instruções', 'sent': sent})


@never_cache
@sensitive_post_parameters('token', 'new_password', 'new_password_confirm')
@require_http_methods(['GET', 'POST'])
def password_reset_confirm(request):
    reset_key = 'agrohub_password_reset'
    incoming = {name: request.GET.get(name, '') for name in ('uid', 'token')}
    if request.method == 'GET' and any(incoming.values()):
        if all(incoming.values()) and len(incoming['uid']) <= 256 and len(incoming['token']) <= 512:
            request.session[reset_key] = {**incoming, 'expires': time()+1800}
        else:
            request.session.pop(reset_key, None)
        response = redirect('accounts:password-reset-confirm')
    else:
        initial = request.session.get(reset_key, {})
        if initial.get('expires', 0) <= time():
            request.session.pop(reset_key, None)
            initial = {}
        data = request.POST.copy() if request.method == 'POST' else None
        if data is not None:
            for name in ('uid', 'token'):
                if not data.get(name) and initial.get(name):
                    data[name] = initial[name]
        form = PasswordResetConfirmForm(data, initial=initial)
        if initial.get('token'):
            form.fields['token'].widget = RedactedHiddenInput()
        if request.method == 'POST' and form.is_valid():
            try:
                AgroHubClient().request('POST', 'password-reset/confirm/', data=form.cleaned_data)
            except AgroHubError as error:
                add_api_errors(form, error)
            else:
                logout(request)
                messages.success(request, 'Senha atualizada. Entre com a nova senha do AgroHub.')
                response = redirect('accounts:login')
                response['Referrer-Policy'] = 'same-origin'
                return response
        response = render(request, 'accounts/remote_form.html', {'form': form, 'title': 'Definir nova senha',
                          'intro': 'Use o UID e o token enviados pelo AgroHub.', 'button': 'Atualizar senha'})
    # O link com segredo nunca vira Referer. Na página limpa, same-origin mantém
    # o Origin válido do POST com CSRF também no desenvolvimento HTTP.
    response['Referrer-Policy'] = 'no-referrer' if request.method == 'GET' and any(incoming.values()) else 'same-origin'
    return response
