from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView, View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.agenda.forms import BookingForm, CancelForm, ReviewForm
from inovalab_app.agenda.modal import booking_saved, render_booking
from inovalab_app.agenda.models import BOOKING_STATUSES, CATEGORIES
from inovalab_app.agenda.policies import ADMIN_CANCEL_MESSAGE, can_access_agenda, can_create_booking, can_cancel_booking
from inovalab_app.agenda.selectors import calendar_weeks, filter_bookings, month_bounds, visible_bookings, visible_booking
from inovalab_app.agenda.services import PUBLIC_FIELDS, SERVICE_FIELDS, BookingConflict, cancel_booking, review_booking, save_booking
from inovalab_app.adapters.host import profile_photo_response, has_profile_photo


class AgendaAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_access_agenda(request.user):
            raise PermissionDenied('Entre com uma conta ativa para acessar a agenda.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return visible_bookings(self.request.user)

    def get_object(self, queryset=None):
        return visible_booking(self.request.user, self.kwargs['category'], self.kwargs['pk'])


class AdminAgendaAccessMixin(AgendaAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_business_admin(request.user):
            raise PermissionDenied('Somente administradores do laboratório podem gerenciar a agenda.')
        return super().dispatch(request, *args, **kwargs)


class BookingWriteAccessMixin(AgendaAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if 'pk' in kwargs:
            return super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and not can_create_booking(request.user):
            raise PermissionDenied('Entre com uma conta ativa para criar agendamentos.')
        return LoginRequiredMixin.dispatch(self, request, *args, **kwargs)


class BookingListView(AgendaAccessMixin, ListView):
    template_name = 'inovalab_app/agenda/list.html'
    paginate_by = 25

    def get_default_month(self):
        return timezone.localdate().strftime('%Y-%m') if is_business_admin(self.request.user) else ''

    def get_default_situation(self):
        return ''

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as error:
            return render(request, 'inovalab_app/agenda/error.html', {'message': ' '.join(error.messages)}, status=400)

    def get_queryset(self):
        self.month = self.request.GET.get('mes', self.get_default_month())
        if self.month:
            month_bounds(self.month)
        self.calendar_month = self.month or timezone.localdate().strftime('%Y-%m')
        self.situation = self.request.GET.get('situacao', self.get_default_situation())
        self.category = self.request.GET.get('categoria', '')
        self.query = self.request.GET.get('q', '').strip()[:150]
        queryset = filter_bookings(sorted(super().get_queryset(), key=lambda row: (row.inicio, row.categoria, row.pk)), month=self.month, category=self.category, situation=self.situation)
        if self.query:
            queryset = [row for row in queryset if self.query.casefold() in ' '.join((
                row.criador_nome, getattr(getattr(row, 'criado_por', None), 'username', ''),
                row.objeto_nome, row.motivo,
            )).casefold()]
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(month=self.month, selected_category=self.category, categories=CATEGORIES.items(),
                       calendar_month=self.calendar_month, selected_situation=self.situation,
                       situations=BOOKING_STATUSES.items(), query=self.query,
                       weeks=calendar_weeks(filter_bookings(self.object_list, month=self.calendar_month), self.calendar_month),
                       category_counts={name: sum(row.situacao == 'confirmado' and row.categoria == name for row in self.object_list)
                                        for name in CATEGORIES})
        return context


class BookingDetailView(AgendaAccessMixin, DetailView):
    context_object_name = 'booking'
    template_name = 'inovalab_app/agenda/detail.html'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'events': self.object.eventos.all()[:5],
                'creator_name': self.object.criador_nome,
                'creator_has_photo': has_profile_photo(self.object.criado_por),
                'can_cancel_booking': can_cancel_booking(self.request.user, self.object)}


@method_decorator(never_cache, name='dispatch')
class BookingCreatorPhotoView(AgendaAccessMixin, View):
    def get(self, request, pk, category):
        booking = self.get_object()
        if not booking.criado_por or not has_profile_photo(booking.criado_por):
            raise Http404
        return profile_photo_response(booking.criado_por)


class BookingWriteView(BookingWriteAccessMixin, View):
    def get_booking(self):
        if 'pk' in self.kwargs and not is_business_admin(self.request.user):
            raise PermissionDenied('Somente administradores do laboratório podem editar agendamentos.')
        booking = self.get_object() if 'pk' in self.kwargs else None
        return booking

    def get(self, request, **kwargs):
        booking = self.get_booking()
        if booking is None:
            category = request.GET.get('categoria', '')
            if category == 'visita':
                return redirect('agenda:visit-create')
            if category not in ('servico', 'equipamento'):
                return render_booking(request, 'inovalab_app/agenda/choose_category.html', {
                    'category_error': 'Selecione uma das formas de agendamento abaixo.' if category else '',
                }, status=400 if category else 200)
        form = BookingForm(booking=booking, actor=request.user,
                           initial={'categoria': request.GET['categoria']} if booking is None else {})
        return render_booking(request, 'inovalab_app/agenda/form.html', {'form': form, 'booking': booking})

    def post(self, request, **kwargs):
        if kwargs.get('category') == 'visita' or (
                'pk' not in kwargs and request.POST.get('categoria') == 'visita'):
            from inovalab_app.agenda.visit_views import VisitWriteView
            return VisitWriteView.as_view()(request, **kwargs)
        booking = self.get_booking()
        if request.POST.get('atualizar') == '1':
            # POST keeps names, reasons and CSRF tokens out of URL/history/logs.
            initial = {key: request.POST[key] for key in PUBLIC_FIELDS | {'dia', 'hora_inicio', 'hora_termino'}
                       if key in request.POST}
            if initial.get('categoria') == 'servico':
                initial['equipamentos'] = request.POST.getlist('equipamentos')
            else:
                for key in SERVICE_FIELDS:
                    initial.pop(key, None)
            if booking:
                initial['versao'] = request.POST.get('versao', '')
            initial.pop('objeto', None)
            if booking and initial.get('categoria') != booking.categoria:
                initial['objeto'] = None
            form = BookingForm(booking=booking, actor=request.user, initial=initial)
            return render_booking(request, 'inovalab_app/agenda/form.html', {'form': form, 'booking': booking})
        form = BookingForm(request.POST, booking=booking, actor=request.user)
        response_status = 200
        if form.is_valid():
            try:
                saved = save_booking(actor=request.user,
                                     data={key: value for key, value in form.cleaned_data.items() if key in PUBLIC_FIELDS},
                                     category=booking.categoria if booking else None, booking_id=booking.pk if booking else None, expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                form.add_error(None, str(error))
                response_status = 409
            except ValidationError as error:
                for field, errors in error.message_dict.items():
                    field = {'inicio': 'hora_inicio', 'fim': 'hora_termino', 'data': 'dia'}.get(field, field)
                    form.add_error(field if field in form.fields else None, errors)
            else:
                return booking_saved(request, saved, creating=booking is None)
        return render_booking(request, 'inovalab_app/agenda/form.html', {'form': form, 'booking': booking}, status=response_status)


class BookingCancelView(AgendaAccessMixin, View):
    def get_object(self, queryset=None):
        booking = super().get_object(queryset)
        if not can_cancel_booking(self.request.user, booking):
            raise PermissionDenied(ADMIN_CANCEL_MESSAGE)
        return booking

    def get(self, request, pk, category):
        booking = self.get_object()
        return render(request, 'inovalab_app/agenda/cancel.html', {'booking': booking, 'form': CancelForm(initial={'versao': booking.versao})})

    def post(self, request, pk, category):
        booking = self.get_object()
        form = CancelForm(request.POST)
        response_status = 400
        message = 'Informe a versão válida do agendamento e confira os campos enviados.'
        if form.is_valid():
            try:
                saved = cancel_booking(actor=request.user, category=category, booking_id=pk, expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                message, response_status = str(error), 409
            else:
                messages.success(request, 'Agendamento cancelado. Horário liberado e histórico preservado.')
                return redirect('agenda:requests' if is_business_admin(request.user) else 'agenda:mine')
        return render(request, 'inovalab_app/agenda/error.html', {'message': message, 'booking': booking}, status=response_status)


class BookingHistoryView(AgendaAccessMixin, ListView):
    template_name = 'inovalab_app/agenda/history.html'
    paginate_by = 25

    def get_queryset(self):
        self.booking = self.get_object()
        return self.booking.eventos.all()

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'booking': self.booking}


@method_decorator(never_cache, name='dispatch')
class BookingReviewListView(AdminAgendaAccessMixin, ListView):
    template_name = 'inovalab_app/agenda/requests.html'
    paginate_by = 25
    http_method_names = ['get', 'head', 'options']

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as error:
            return render(request, 'inovalab_app/agenda/error.html', {'message': ' '.join(error.messages)}, status=400)

    def get_queryset(self):
        from inovalab_app.agenda.models import BOOKING_MODELS
        from inovalab_app.agenda.personal import PersonalBooking
        self.query = self.request.GET.get('q', '').strip()[:150]
        self.month = self.request.GET.get('mes', '')
        self.selected_status = self.request.GET.get('status', '')
        if self.selected_status not in ('', 'pendente', 'confirmada', 'cancelada', 'recusada'):
            raise ValidationError('Selecione uma situação válida.')
        bounds = month_bounds(self.month) if self.month else None
        rows = [PersonalBooking(row) for model in BOOKING_MODELS.values()
                for row in model.objects.select_related('criado_por').all()]
        if bounds:
            start, end = bounds
            rows = [row for row in rows if row.inicio < end and row.fim > start]
        if self.query:
            rows = [row for row in rows if self.query.casefold() in ' '.join((
                str(row.pk), row.categoria_display, row.objeto_nome, row.criador_nome,
                row.motivo, row.observacoes)).casefold()]
        self.reservations = sorted(rows, key=lambda row: (row.inicio, row.categoria, row.pk), reverse=True)
        status = {'confirmada': 'confirmado', 'cancelada': 'cancelado',
                  'recusada': 'rejeitado'}.get(self.selected_status, self.selected_status)
        return [row for row in self.reservations if not status or row.situacao == status]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        columns = [{'status': status, 'label': label, 'tone': tone,
                    'count': sum(row.situacao == situation for row in self.reservations),
                    'bookings': [row for row in context['object_list'] if row.situacao == situation]}
                   for status, situation, label, tone in (
                       ('pendente', 'pendente', 'Pendentes', 'criacao'),
                       ('confirmada', 'confirmado', 'Confirmadas', 'concluido'),
                       ('cancelada', 'cancelado', 'Canceladas', 'canceladas'),
                       ('recusada', 'rejeitado', 'Recusadas', 'avaliacao'))]
        return {**context, 'query': self.query, 'month': self.month, 'selected_status': self.selected_status,
                'columns': columns, 'stat_counts': {'all': len(self.reservations),
                                                   **{column['status']: column['count'] for column in columns}}}


class BookingReviewView(AdminAgendaAccessMixin, View):
    def post(self, request, pk, category):
        booking = self.get_object()
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return render(request, 'inovalab_app/agenda/error.html', {'message': 'Confira a decisão, a versão e os campos enviados.',
                                                       'booking': booking}, status=400)
        try:
            saved = review_booking(actor=request.user, category=category, booking_id=pk, expected_version=form.cleaned_data['versao'],
                           decision=form.cleaned_data['decisao'])
        except BookingConflict as error:
            return render(request, 'inovalab_app/agenda/error.html', {'message': str(error), 'booking': booking}, status=409)
        except ValidationError as error:
            return render(request, 'inovalab_app/agenda/error.html', {'message': ' '.join(error.messages), 'booking': booking}, status=400)
        messages.success(request, 'Solicitação aceita. Horário reservado.' if form.cleaned_data['decisao'] == 'aprovar'
                         else 'Solicitação rejeitada.')
        return redirect('agenda:requests')
