from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers

from inovalab_app.adapters.host import can_access_panel, is_business_admin


def render_booking(request, template, context=None, *, status=200):
    context = {**(context or {}), 'form_action': request.path}
    if not can_access_panel(request.user):
        context['booking_base'] = 'inovalab_app/agenda/public_base.html'
    if not context.get('booking') and request.headers.get('X-Booking-Modal') == '1':
        context.update(booking_modal=True, booking_base='inovalab_app/agenda/modal_base.html')
    response = render(request, template, context, status=status)
    patch_vary_headers(response, ['X-Booking-Modal'])
    response['Cache-Control'] = 'no-store'
    return response


def booking_saved(request, booking, *, creating):
    next_url = (reverse('tarefas:confirm-service', kwargs={'pk': booking.pk})
                if creating and booking.categoria == 'servico' and is_business_admin(request.user) else None)
    if can_access_panel(request.user):
        detail_url = booking.get_absolute_url()
    elif booking.categoria == 'visita':
        detail_url = reverse('agenda:my-visit-detail', kwargs={'pk': booking.pk})
    else:
        detail_url = reverse('agenda:my-detail', kwargs={'category': booking.categoria, 'pk': booking.pk})
    message = ('Solicitação enviada. Aguarde a confirmação de um administrador.'
               if booking.situacao == 'pendente' else 'Agendamento salvo.')
    if next_url:
        message = 'Serviço registrado como pendente. Crie a tarefa para confirmar o agendamento.'
    if creating and request.headers.get('X-Booking-Modal') == '1':
        response = JsonResponse({'created': True, 'message': message,
                                 'detail_url': detail_url, **({'next_url': next_url} if next_url else {})}, status=201)
        response['Cache-Control'] = 'no-store'
        return response
    messages.success(request, message)
    return redirect(next_url or detail_url)
