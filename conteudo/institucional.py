from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from accounts.agrohub.client import AgroHubClient, AgroHubError
from conteudo.contact_forms import ContactForm
from conteudo.institutional_content import ABOUT_TIMELINE, EQUIPMENT, INOVALAB_STATS, SERVICES, TEAM_MEMBERS
from conteudo.selectors import published_banners


def _page(request, template, local, **extra):
    banner = published_banners(local).first() if local in ('home', 'sobre') else None
    hero = {'image': {'url': reverse('conteudo:image', args=[banner.pk])},
            'title': banner.titulo, 'alt_text': banner.texto_alternativo} if banner else None
    return render(request, 'conteudo/institucional/'+template+'.html', {
        'local': local, 'hero_banner': hero,
        'inovalab_stats': INOVALAB_STATS, 'featured_equipment': EQUIPMENT,
        'about_timeline': ABOUT_TIMELINE, 'team_members': TEAM_MEMBERS, 'services': SERVICES,
        **extra,
    })


@never_cache
@require_safe
def inicio(request):
    return _page(request, 'home', 'home')


@never_cache
@require_safe
def sobre(request):
    return _page(request, 'about', 'sobre')


@never_cache
@require_safe
def servicos(request):
    return _page(request, 'programs', 'servicos')


@never_cache
@require_http_methods(['GET', 'POST'])
def contato(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {'nome': request.user.get_full_name() or request.user.username, 'email': request.user.email}
    form = ContactForm(request.POST if request.method == 'POST' else None, initial=initial)
    response_status = 200
    if request.method == 'POST':
        response_status = 400
        if form.is_valid():
            payload = {name: form.cleaned_data[name] for name in ('nome', 'email', 'telefone', 'mensagem')}
            payload.update(site_code='inovalab', assunto='Contato pelo site InovaLab')
            try:
                result = AgroHubClient().request('POST', '', namespace='contact', data=payload)
                if type(result.get('id')) is not int or result['id'] <= 0:
                    raise AgroHubError()
            except AgroHubError as error:
                added = False
                for name, errors in error.errors.items():
                    if name in ('nome', 'email', 'telefone', 'mensagem') and errors:
                        form.add_error(name, errors)
                        added = True
                if not added:
                    form.add_error(None, 'Não foi possível confirmar o recebimento da mensagem. '
                                   'Se o problema persistir, entre em contato por telefone ou e-mail.')
                response_status = 400 if error.status in (400, 422) else 429 if error.status == 429 else 503
            else:
                messages.success(request, 'Mensagem recebida pelo InovaLab. Nossa equipe retornará em breve.')
                return redirect('conteudo:contato')
    for field in form:
        if field.errors:
            field.field.widget.attrs.update({'aria-invalid': 'true',
                                             'aria-describedby': field.id_for_label+'_error'})
    response = _page(request, 'contact', 'contato', contact_form=form)
    response.status_code = response_status
    return response
