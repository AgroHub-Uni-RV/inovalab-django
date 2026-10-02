from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView, View

from accounts.policies import is_business_admin
from agenda.forms import BookingForm, CancelForm
from agenda.models import CATEGORIES, Agendamento
from agenda.selectors import calendar_weeks, filter_bookings, month_bounds, visible_bookings
from agenda.services import PUBLIC_FIELDS, BookingConflict, cancel_booking, save_booking


class AgendaAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_business_admin(request.user):
            raise PermissionDenied('Somente administradores do laboratório podem acessar a agenda.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return visible_bookings(self.request.user)


class BookingListView(AgendaAccessMixin, ListView):
    template_name = 'agenda/list.html'
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as error:
            return render(request, 'agenda/error.html', {'message': ' '.join(error.messages)}, status=400)

    def get_queryset(self):
        self.month = self.request.GET.get('mes') or timezone.localdate().strftime('%Y-%m')
        month_bounds(self.month)
        self.category = self.request.GET.get('categoria', '')
        return filter_bookings(super().get_queryset(), month=self.month, category=self.category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(month=self.month, selected_category=self.category, categories=CATEGORIES.items(),
                       weeks=calendar_weeks(self.object_list, self.month))
        return context


class BookingDetailView(AgendaAccessMixin, DetailView):
    model = Agendamento
    context_object_name = 'booking'
    template_name = 'agenda/detail.html'


class BookingWriteView(AgendaAccessMixin, View):
    def get_booking(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['pk']) if 'pk' in self.kwargs else None

    def get(self, request, **kwargs):
        booking = self.get_booking()
        form = BookingForm(booking=booking, initial={'categoria': request.GET['categoria']} if 'categoria' in request.GET else {})
        return render(request, 'agenda/form.html', {'form': form, 'booking': booking})

    def post(self, request, **kwargs):
        booking = self.get_booking()
        if request.POST.get('atualizar') == '1':
            # POST keeps names, reasons and CSRF tokens out of URL/history/logs.
            initial = {key: request.POST[key] for key in PUBLIC_FIELDS if key in request.POST}
            if booking:
                initial['versao'] = request.POST.get('versao', '')
            initial.pop('objeto', None)
            if booking and initial.get('categoria') != booking.categoria:
                initial['objeto'] = None
            form = BookingForm(booking=booking, initial=initial)
            return render(request, 'agenda/form.html', {'form': form, 'booking': booking})
        form = BookingForm(request.POST, booking=booking)
        response_status = 200
        if form.is_valid():
            try:
                saved = save_booking(actor=request.user, data={key: form.cleaned_data[key] for key in PUBLIC_FIELDS},
                                     booking_id=booking.pk if booking else None, expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                form.add_error(None, str(error))
                response_status = 409
            except ValidationError as error:
                for field, errors in error.message_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                messages.success(request, 'Agendamento salvo.')
                return redirect('agenda:detail', pk=saved.pk)
        return render(request, 'agenda/form.html', {'form': form, 'booking': booking}, status=response_status)


class BookingCancelView(AgendaAccessMixin, View):
    def get(self, request, pk):
        booking = get_object_or_404(self.get_queryset(), pk=pk)
        return render(request, 'agenda/cancel.html', {'booking': booking, 'form': CancelForm(initial={'versao': booking.versao})})

    def post(self, request, pk):
        booking = get_object_or_404(self.get_queryset(), pk=pk)
        form = CancelForm(request.POST)
        response_status = 400
        message = 'Informe a versão válida do agendamento e confira os campos enviados.'
        if form.is_valid():
            try:
                cancel_booking(actor=request.user, booking_id=pk, expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                message, response_status = str(error), 409
            else:
                messages.success(request, 'Agendamento cancelado. Horário liberado e histórico preservado.')
                return redirect('agenda:list')
        return render(request, 'agenda/error.html', {'message': message, 'booking': booking}, status=response_status)


class BookingHistoryView(AgendaAccessMixin, ListView):
    template_name = 'agenda/history.html'
    paginate_by = 25

    def get_queryset(self):
        self.booking = get_object_or_404(visible_bookings(self.request.user), pk=self.kwargs['pk'])
        return self.booking.eventos.all()

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'booking': self.booking}
