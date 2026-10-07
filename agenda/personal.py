from dataclasses import dataclass

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import ListView

from accounts.agrohub.client import AgroHubError
from accounts.policies import can_access_panel
from agenda.models import CATEGORIES
from agenda.policies import can_view_own_bookings
from agenda.remote_requests import get_reservation, reservations
from agenda.selectors import month_bounds, own_booking, own_bookings


PERSONAL_STATUSES = {'pendente': 'Pendente', 'confirmado': 'Confirmado',
                     'rejeitado': 'Recusado', 'cancelado': 'Cancelado'}


@dataclass(frozen=True)
class PersonalBooking:
    booking: object

    def __getattr__(self, name):
        return getattr(self.booking, name)

    @property
    def situacao(self):
        if self.booking.cancelado_em or self.booking.situacao == 'cancelada':
            return 'cancelado'
        return self.booking.situacao

    def get_situacao_display(self):
        return PERSONAL_STATUSES[self.situacao]

    def get_absolute_url(self):
        if self.categoria == 'visita':
            return reverse('agenda:my-visit-detail', kwargs={'pk': self.pk})
        return reverse('agenda:my-detail', kwargs={'category': self.categoria, 'pk': self.pk})


def personal_context(request):
    return {'personal_base': 'agenda/base.html' if can_access_panel(request.user) else 'agenda/public_base.html'}


def own_visits_available(request):
    # A API amplia owned_by para todas as reservas quando is_staff é verdadeiro,
    # mas não informa o ID do solicitante. Não inferir titularidade pelo nome.
    return (request.user.agrohub_id is not None
            and getattr(request, 'agrohub_profile', {}).get('is_staff') is False)


class OwnBookingAccessMixin(LoginRequiredMixin):
    http_method_names = ['get', 'head', 'options']

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_own_bookings(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


@method_decorator(never_cache, name='dispatch')
class MyBookingsListView(OwnBookingAccessMixin, ListView):
    template_name = 'agenda/my_bookings.html'
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as error:
            return render(request, 'agenda/my_error.html', {
                **personal_context(request), 'message': ' '.join(error.messages),
            }, status=400)

    def get_queryset(self):
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
        rows = own_bookings(self.request.user)
        self.visits_warning = ''
        if own_visits_available(self.request):
            try:
                rows.extend(reservations(self.request))
            except AgroHubError:
                self.visits_warning = 'Não foi possível consultar suas visitas no AgroHub. Seus agendamentos locais continuam disponíveis.'
        else:
            self.visits_warning = ('Suas visitas não estão disponíveis para consulta individual nesta conta. '
                                   'Seus agendamentos locais estão disponíveis abaixo.' if self.request.user.agrohub_id is not None
                                   else 'Vincule sua conta ao AgroHub para consultar também suas visitas.')
        result = [PersonalBooking(row) for row in rows]
        if self.category:
            result = [row for row in result if row.categoria == self.category]
        if self.status:
            result = [row for row in result if row.situacao == self.status]
        if bounds:
            start, end = bounds
            result = [row for row in result if row.inicio < end and row.fim > start]
        if self.query:
            result = [row for row in result if self.query.casefold() in ' '.join((
                str(row.pk), row.objeto_nome, row.motivo, row.observacoes, getattr(row, 'sala', ''),
            )).casefold()]
        return sorted(result, key=lambda row: (row.inicio, row.categoria, row.pk), reverse=True)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **personal_context(self.request),
                'query': self.query, 'month': self.month, 'selected_category': self.category,
                'selected_situation': self.status, 'categories': CATEGORIES.items(),
                'situations': PERSONAL_STATUSES.items(), 'visits_warning': self.visits_warning}


@method_decorator(never_cache, name='dispatch')
class MyBookingDetailView(OwnBookingAccessMixin, View):
    def get(self, request, category=None, pk=None):
        if category is None:
            if not own_visits_available(request):
                raise Http404
            try:
                booking = get_reservation(request, pk)
            except AgroHubError as error:
                if error.status == 404:
                    raise Http404 from error
                return render(request, 'agenda/my_error.html', {
                    **personal_context(request), 'message': 'Não foi possível consultar esta visita no AgroHub.',
                }, status=403 if error.status in (401, 403) else 503)
            events = []
        else:
            booking = own_booking(request.user, category, pk)
            events = booking.eventos.all()
        return render(request, 'agenda/my_detail.html', {
            **personal_context(request), 'booking': PersonalBooking(booking), 'events': events,
        })
