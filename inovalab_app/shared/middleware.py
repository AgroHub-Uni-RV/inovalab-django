from urllib.parse import urlencode
from django.http import JsonResponse
from django.shortcuts import redirect, render
from inovalab_app.adapters.host import can_access_panel, get_adapter
from inovalab_app.agenda.policies import can_create_booking, can_view_own_bookings


class InovalabAccessMiddleware:
    INTERNAL_NAMESPACES = {'core', 'catalogo', 'tarefas', 'agenda', 'materiais'}
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
        access = getattr(view_func, 'inovalab_access', None)
        if access == 'public':
            return None
        if namespace == 'agenda' and name in self.PERSONAL_AGENDA_NAMES and can_view_own_bookings(request.user):
            return None
        if can_create_booking(request.user):
            if namespace == 'agenda' and name in {'create', 'visit-create'}:
                return None
            if namespace == 'catalogo' and name == 'equipment-photo' and request.method in {'GET', 'HEAD'}:
                return None
            if access == 'booking' and getattr(view_func, 'actions', {}).get(request.method.lower()) in {'create', 'destroy'}:
                return None
        protected = (namespace in self.INTERNAL_NAMESPACES
                     or (namespace == 'conteudo' and name not in self.PUBLIC_CONTENT_NAMES)
                     or access in {'internal', 'booking'})
        if protected and not can_access_panel(request.user):
            return self.denied(request, api=access is not None)
        return None

    def denied(self, request, *, api=False):
        if api:
            response = JsonResponse({'detail': 'Acesso restrito à equipe e aos administradores do AgroHub.'}, status=403)
        elif not request.user.is_authenticated:
            return redirect(get_adapter().identity_context(request)['login_url']+'?'+urlencode({'next': request.get_full_path()}))
        else:
            response = render(request, 'inovalab_app/shared/access_denied.html', status=403)
        response['Cache-Control'] = 'no-store'
        return response
