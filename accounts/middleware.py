from urllib.parse import urlencode

from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.agrohub.client import AgroHubError
from accounts.agrohub.services import authenticated_request, sync_profile
from accounts.policies import can_access_panel, is_technical_admin
from inovalab_app.shared.middleware import InovalabAccessMiddleware


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


class InternalAccessMiddleware(InovalabAccessMiddleware):
    """Standalone host adds technical Accounts/Admin protection."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match is not None:
            technical = match.namespace == 'admin' and match.url_name not in ('login', 'logout')
            users = match.namespace == 'accounts' and match.url_name == 'users'
            if (technical or users) and not is_technical_admin(request.user):
                return self.denied(request)
        return super().process_view(request, view_func, view_args, view_kwargs)