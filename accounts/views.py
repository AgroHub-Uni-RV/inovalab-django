from urllib.parse import urljoin, urlsplit

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from accounts.policies import is_business_admin
from accounts.forms import ProfileForm
from accounts.models import User


class AccountLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        destination = super().get_success_url()
        # Keep Django's host/scheme validation, then prevent returns to either entry.
        path = urlsplit(urljoin(self.request.build_absolute_uri(), destination)).path
        if path in (reverse('accounts:login'), reverse('accounts:login-alias')):
            return self.get_default_redirect_url()
        return destination


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def home(request: HttpRequest) -> HttpResponse:
    form = ProfileForm(request.POST if request.method == 'POST' else None,
                       request.FILES if request.method == 'POST' else None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save(commit=False).save(update_fields=['username', 'first_name', 'last_name', 'foto'])
        except IntegrityError:
            form.add_error('username', 'Este nome de usuário já está em uso. Escolha outro.')
        else:
            messages.success(request, 'Perfil atualizado com sucesso.')
            return redirect('accounts:home')
    return render(request, 'accounts/home.html', {
        'is_business_admin': is_business_admin(request.user),
        'form': form,
    })


@never_cache
@login_required
@require_safe
def profile_photo(request, pk):
    if request.user.pk != pk and not request.user.is_superuser:
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk)
    if not user.foto:
        raise Http404
    try:
        stream = user.foto.open('rb')
    except OSError as error:
        raise Http404 from error
    response = FileResponse(stream, content_type='image/webp')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
