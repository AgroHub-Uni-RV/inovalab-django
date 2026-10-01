from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from accounts.policies import is_business_admin


@login_required
def home(request: HttpRequest) -> HttpResponse:
    return render(request, 'accounts/home.html', {
        'is_business_admin': is_business_admin(request.user),
    })
