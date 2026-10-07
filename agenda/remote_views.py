from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from accounts.agrohub.client import AgroHubError
from accounts.policies import is_business_admin
from agenda.remote_forms import RemoteVisitForm
from agenda.remote_requests import available_rooms, cancel_reservation, get_reservation, save_reservation
from agenda.views import AgendaAccessMixin


def visit_error(request, error):
    status = error.status
    if status in (401, 403):
        status, message = 403, 'Sua conta não tem permissão para esta visita. Entre com uma conta vinculada ao AgroHub.'
    elif status == 404:
        message = 'A visita não está disponível no AgroHub.'
    elif status == 409:
        message = 'A situação ou o horário da visita não permite esta ação. Consulte suas visitas no AgroHub.'
    elif status in (400, 422):
        status, message = 400, 'O AgroHub recusou a operação. Confira os dados e a situação da visita.'
    else:
        status, message = 503, 'Não foi possível confirmar o resultado no AgroHub; consulte suas visitas antes de tentar novamente.'
    return render(request, 'agenda/remote_error.html', {'message': message}, status=status)


def may_edit(user, booking):
    return is_business_admin(user) or booking.status == 'pendente'


def may_cancel(booking):
    return booking.status in ('pendente', 'confirmada') and booking.inicio >= timezone.now()


@method_decorator(never_cache, name='dispatch')
class RemoteVisitView(AgendaAccessMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.agrohub_id is None:
            return visit_error(request, AgroHubError(403))
        try:
            return super().dispatch(request, *args, **kwargs)
        except AgroHubError as error:
            return visit_error(request, error)


class RemoteBookingDetailView(RemoteVisitView):
    def get(self, request, pk):
        booking = get_reservation(request, pk)
        return render(request, 'agenda/remote_detail.html', {'booking': booking,
                       'may_edit': may_edit(request.user, booking), 'may_cancel': may_cancel(booking)})


class RemoteBookingWriteView(RemoteVisitView):
    def booking(self, request, pk):
        if pk is None:
            return None
        booking = get_reservation(request, pk)
        if not may_edit(request.user, booking):
            raise PermissionDenied('Somente visitas pendentes podem ser editadas pela equipe.')
        return booking

    def get(self, request, pk=None):
        booking = self.booking(request, pk)
        form = RemoteVisitForm(booking=booking, rooms=available_rooms(request) if booking is None else ())
        return render(request, 'agenda/remote_form.html', {'form': form, 'booking': booking})

    def post(self, request, pk=None):
        booking = self.booking(request, pk)
        form = RemoteVisitForm(request.POST, booking=booking,
                               rooms=available_rooms(request) if booking is None else ())
        if not form.is_valid():
            return render(request, 'agenda/remote_form.html', {'form': form, 'booking': booking}, status=400)
        try:
            remote = save_reservation(request, form.payload(), reservation_id=pk)
        except AgroHubError as error:
            if error.status in (400, 422) and error.errors:
                for name, errors in error.errors.items():
                    form.add_error(name if name in form.fields else None, errors)
                return render(request, 'agenda/remote_form.html', {'form': form, 'booking': booking}, status=400)
            raise
        messages.success(request, 'Visita salva no AgroHub. Aguarde a confirmação.' if remote.status == 'pendente'
                         else 'Visita salva no AgroHub. Disponível na agenda de visitas.')
        return redirect(remote)


class RemoteBookingCancelView(RemoteVisitView):
    def get(self, request, pk):
        booking = get_reservation(request, pk)
        if not may_cancel(booking):
            raise AgroHubError(409)
        return render(request, 'agenda/remote_cancel.html', {'booking': booking})

    def post(self, request, pk):
        if (set(request.POST) - {'csrfmiddlewaretoken'}
                or any(len(request.POST.getlist(key)) != 1 for key in request.POST)):
            raise AgroHubError(400)
        booking = cancel_reservation(request, pk)
        messages.success(request, 'Visita cancelada no AgroHub.')
        return redirect(booking)
