from urllib.parse import urljoin, urlsplit

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from accounts.policies import is_business_admin


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


@login_required
def home(request: HttpRequest) -> HttpResponse:
    return render(request, 'accounts/home.html', {
        'is_business_admin': is_business_admin(request.user),
    })
