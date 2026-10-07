from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers

from accounts.policies import can_access_panel


def render_booking(request, template, context=None, *, status=200):
    context = {**(context or {}), 'form_action': request.path}
    if not can_access_panel(request.user):
        context['booking_base'] = 'agenda/public_base.html'
    if not context.get('booking') and request.headers.get('X-Booking-Modal') == '1':
        context.update(booking_modal=True, booking_base='agenda/modal_base.html')
    response = render(request, template, context, status=status)
    patch_vary_headers(response, ['X-Booking-Modal'])
    response['Cache-Control'] = 'no-store'
    return response


def booking_saved(request, booking, *, creating):
    if can_access_panel(request.user):
        detail_url = booking.get_absolute_url()
    elif booking.categoria == 'visita':
        detail_url = reverse('agenda:my-visit-detail', kwargs={'pk': booking.pk})
    else:
        detail_url = reverse('agenda:my-detail', kwargs={'category': booking.categoria, 'pk': booking.pk})
    message = ('Solicitação enviada. Aguarde a confirmação de um administrador.'
               if booking.situacao == 'pendente' else 'Agendamento salvo.')
    if creating and request.headers.get('X-Booking-Modal') == '1':
        response = JsonResponse({'created': True, 'message': message,
                                 'detail_url': detail_url}, status=201)
        response['Cache-Control'] = 'no-store'
        return response
    messages.success(request, message)
    return redirect(detail_url)
