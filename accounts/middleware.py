from urllib.parse import urlencode

from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.agrohub.client import AgroHubError
from accounts.agrohub.services import authenticated_request, sync_profile
from accounts.policies import can_access_panel, is_technical_admin
from agenda.policies import can_view_own_bookings, can_create_booking


class AgroHubSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public_paths = {reverse(name) for name in ('accounts:logout', 'accounts:password-reset',
                                                  'accounts:password-reset-confirm',
                                                  'conteudo:inicio', 'conteudo:sobre',
                                                  'conteudo:servicos', 'conteudo:contato',
                                                  'conteudo:regimento', 'conteudo:calendario-funcionamento')}
        if request.user.is_authenticated and request.user.agrohub_id is not None and request.path not in public_paths:
            try:
                profile = authenticated_request(request, 'GET', 'me/')
                sync_profile(request.user, profile)
                request.agrohub_profile = profile
            except AgroHubError as error:
                if error.status in (400, 401, 403):
                    logout(request)
                    if request.path.startswith('/api/'):
                        return JsonResponse({'detail': 'Entre novamente pelo AgroHub.'}, status=403)
                    return redirect(reverse('accounts:login')+'?'+urlencode({'next': request.get_full_path()}))
                if request.path.startswith('/api/'):
                    return JsonResponse({'detail': str(error)}, status=503)
                return render(request, 'accounts/provider_error.html', status=503)
        return self.get_response(request)


class InternalAccessMiddleware:
    """Protege rotas internas antes de executar views e APIs de sessão."""

    INTERNAL_NAMESPACES = {'core', 'catalogo', 'tarefas', 'agenda', 'materiais', 'integracoes',
                           'catalogo_api', 'tarefas_api', 'agenda_api', 'materiais_api'}
    PUBLIC_CONTENT_NAMES = {'inicio', 'sobre', 'servicos', 'contato', 'regimento',
                            'calendario-funcionamento', 'public-home', 'public-about', 'image'}
    PERSONAL_AGENDA_NAMES = {'mine', 'my-detail', 'my-visit-detail', 'visit-list', 'my-cancel'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match is None:
            return None
        namespace, name = match.namespace, match.url_name or ''
        if (namespace == 'agenda' and name in self.PERSONAL_AGENDA_NAMES
                and can_view_own_bookings(request.user)):
            return None
        api_class = getattr(view_func, 'cls', None)
        if can_create_booking(request.user):
            if namespace == 'agenda' and name in {'create', 'visit-create'}:
                return None
            if namespace == 'catalogo' and name == 'equipment-photo' and request.method in {'GET', 'HEAD'}:
                return None
            if (api_class is not None and api_class.__module__ == 'agenda.api'
                    and getattr(view_func, 'actions', {}).get(request.method.lower()) in {'create', 'destroy'}):
                return None
        internal_api = (api_class is not None
                        and api_class.__module__ in {'catalogo.api', 'tarefas.api', 'agenda.api',
                                                    'materiais.api', 'conteudo.api'}
                        and api_class.__name__ != 'PublicBannerListView')
        protected = (namespace in self.INTERNAL_NAMESPACES
                     or (namespace == 'conteudo' and name not in self.PUBLIC_CONTENT_NAMES)
                     or (namespace == 'accounts' and name == 'users')
                     or (not namespace and name.startswith('banner-')) or internal_api)
        # Integrações externas usam credencial própria e mantêm sua autenticação.
        technical = namespace == 'admin' and name not in ('login', 'logout')
        allowed = is_technical_admin(request.user) if technical else can_access_panel(request.user)
        if not (protected or technical) or allowed:
            return None
        if request.path.startswith('/api/'):
            response = JsonResponse({'detail': 'Acesso restrito à equipe e aos administradores do AgroHub.'}, status=403)
            response['Cache-Control'] = 'no-store'
            return response
        if not request.user.is_authenticated:
            return redirect(reverse('accounts:login')+'?'+urlencode({'next': request.get_full_path()}))
        response = render(request, 'accounts/internal_access_denied.html', status=403)
        response['Cache-Control'] = 'no-store'
        return response
