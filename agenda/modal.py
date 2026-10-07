from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.cache import patch_vary_headers


def render_booking(request, template, context=None, *, status=200):
    context = {**(context or {}), 'form_action': request.path}
    if not context.get('booking') and request.headers.get('X-Booking-Modal') == '1':
        context.update(booking_modal=True, booking_base='agenda/modal_base.html')
    response = render(request, template, context, status=status)
    patch_vary_headers(response, ['X-Booking-Modal'])
    response['Cache-Control'] = 'no-store'
    return response


def booking_saved(request, booking, *, creating):
    message = ('Solicitação enviada. Aguarde a confirmação de um administrador.'
               if booking.situacao == 'pendente' else 'Agendamento salvo.')
    if creating and request.headers.get('X-Booking-Modal') == '1':
        response = JsonResponse({'created': True, 'message': message,
                                 'detail_url': booking.get_absolute_url()}, status=201)
        response['Cache-Control'] = 'no-store'
        return response
    messages.success(request, message)
    return redirect(booking)
