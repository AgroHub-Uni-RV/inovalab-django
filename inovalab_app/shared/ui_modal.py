from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def modal_redirect(request, view_name, *args, **kwargs):
    """Successful operations only: errors keep their ordinary HTML/status."""
    if request.headers.get('X-UI-Modal') == '1':
        response = JsonResponse({'saved': True, 'redirect_url': reverse(view_name, args=args or None, kwargs=kwargs or None)})
        response['Cache-Control'] = 'no-store'
        return response
    return redirect(view_name, *args, **kwargs)
