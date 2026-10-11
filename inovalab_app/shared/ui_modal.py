from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def modal_redirect(request, view_name, *args, **kwargs):
    """Successful operations only: errors keep their ordinary HTML/status."""
    destination = reverse(view_name, args=args or None, kwargs=kwargs or None)
    return modal_redirect_url(request, destination)


def modal_redirect_url(request, destination):
    if request.headers.get('X-UI-Modal') == '1':
        response = JsonResponse({'saved': True, 'redirect_url': destination})
        response['Cache-Control'] = 'no-store'
        return response
    return redirect(destination)
