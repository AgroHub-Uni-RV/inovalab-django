from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import ListView

from inovalab_app.adapters.host import can_access_panel, is_business_admin
from inovalab_app.agenda.models import CATEGORIES
from inovalab_app.agenda.execution import EXECUTION_CHOICES, filter_execution, realization_actor_name
from inovalab_app.agenda.forms import CancelForm
from inovalab_app.agenda.policies import ADMIN_CANCEL_MESSAGE, can_view_own_bookings, can_cancel_booking
from inovalab_app.agenda.selectors import occurs_in_period, month_bounds, own_booking, own_bookings
from inovalab_app.agenda.services import BookingConflict, cancel_booking


PERSONAL_STATUSES = {'pendente': 'Pendente', 'confirmado': 'Confirmado',
                     'rejeitado': 'Recusado', 'cancelado': 'Cancelado'}


@dataclass(frozen=True)
class PersonalBooking:
    booking: object

    def __getattr__(self, name):
        return getattr(self.booking, name)

    @property
    def situacao(self):
        if self.booking.cancelado_em:
            return 'cancelado'
        return self.booking.situacao

    def get_situacao_display(self):
        return PERSONAL_STATUSES[self.situacao]

    def get_absolute_url(self):
        if self.categoria == 'visita':
            return reverse('agenda:my-visit-detail', kwargs={'pk': self.pk})
        return reverse('agenda:my-detail', kwargs={'category': self.categoria, 'pk': self.pk})


def personal_context(request):
    return {'personal_base': 'inovalab_app/agenda/base.html' if can_access_panel(request.user) else 'inovalab_app/agenda/public_base.html'}


class OwnBookingAccessMixin(LoginRequiredMixin):
    http_method_names = ['get', 'head', 'options']

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_own_bookings(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


@method_decorator(never_cache, name='dispatch')
class MyBookingsListView(OwnBookingAccessMixin, ListView):
    template_name = 'inovalab_app/agenda/my_bookings.html'
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as error:
            return render(request, 'inovalab_app/agenda/my_error.html', {
                **personal_context(request), 'message': ' '.join(error.messages),
            }, status=400)

    def get_queryset(self):
        self.execution_now = timezone.now()
        self.query = self.request.GET.get('q', '').strip()[:150]
        self.month = self.request.GET.get('mes', '')
        self.category = self.request.GET.get('categoria', '')
        # Mantém filtros de links antigos da página de visitas.
        raw_status = self.request.GET.get('situacao', self.request.GET.get('status', ''))
        self.status = {'confirmada': 'confirmado', 'cancelada': 'cancelado', 'recusada': 'rejeitado'}.get(raw_status, raw_status)
        if self.category and self.category not in CATEGORIES:
            raise ValidationError('Selecione uma categoria válida.')
        if self.status and self.status not in PERSONAL_STATUSES:
            raise ValidationError('Selecione uma situação válida.')
        bounds = month_bounds(self.month) if self.month else None
        self.selected_execution = self.request.GET.get('execucao', '')
        rows = filter_execution(own_bookings(self.request.user, now=self.execution_now), self.selected_execution)
        result = [PersonalBooking(row) for row in rows]
        if self.category:
            result = [row for row in result if row.categoria == self.category]
        if self.status:
            result = [row for row in result if row.situacao == self.status]
        if bounds:
            start, end = bounds
            result = [row for row in result if occurs_in_period(row, start, end)]
        if self.query:
            result = [row for row in result if self.query.casefold() in ' '.join((
                str(row.pk), row.objeto_nome, row.motivo, row.observacoes,
            )).casefold()]
        return sorted(result, key=lambda row: (row.inicio, row.categoria, row.pk), reverse=True)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **personal_context(self.request),
                'query': self.query, 'month': self.month, 'selected_category': self.category,
                'selected_situation': self.status, 'categories': CATEGORIES.items(),
                'situations': PERSONAL_STATUSES.items(),
                'selected_execution': self.selected_execution, 'execution_choices': EXECUTION_CHOICES}


@method_decorator(never_cache, name='dispatch')
class MyBookingDetailView(OwnBookingAccessMixin, View):
    def get(self, request, category=None, pk=None):
        booking = own_booking(request.user, category or 'visita', pk)
        events = booking.eventos.all()
        return render(request, 'inovalab_app/agenda/my_detail.html', {
            **personal_context(request), 'booking': PersonalBooking(booking), 'events': events,
            'can_cancel_booking': can_cancel_booking(request.user, booking),
            'realization_actor_name': realization_actor_name(booking),
        })


@method_decorator(never_cache, name='dispatch')
class MyBookingCancelView(OwnBookingAccessMixin, View):
    http_method_names = ['get', 'post', 'head', 'options']

    def get_booking(self, request, category, pk):
        booking = own_booking(request.user, category, pk)
        if booking.cancelado_em:
            raise Http404
        if not can_cancel_booking(request.user, booking):
            raise PermissionDenied(ADMIN_CANCEL_MESSAGE)
        return booking

    def render_form(self, request, booking, form, *, status=200):
        return render(request, 'inovalab_app/agenda/my_cancel.html', {
            **personal_context(request), 'booking': PersonalBooking(booking), 'form': form,
        }, status=status)

    def get(self, request, category, pk):
        booking = self.get_booking(request, category, pk)
        return self.render_form(request, booking, CancelForm(initial={'versao': booking.versao}))

    def post(self, request, category, pk):
        booking = self.get_booking(request, category, pk)
        form = CancelForm(request.POST)
        status = 400
        if form.is_valid():
            try:
                cancel_booking(actor=request.user, category=category, booking_id=pk,
                               expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                form.add_error(None, str(error))
                status = 409
            else:
                messages.success(request, 'Agendamento cancelado. Horário liberado e histórico preservado.')
                return redirect('agenda:requests' if is_business_admin(request.user) else 'agenda:mine')
        return self.render_form(request, booking, form, status=status)
