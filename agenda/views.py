from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView, View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from accounts.policies import is_business_admin
from agenda.forms import BookingForm, CancelForm, ReviewForm
from agenda.models import BOOKING_STATUSES, CATEGORIES, Agendamento
from agenda.policies import can_access_agenda
from agenda.selectors import calendar_weeks, filter_bookings, month_bounds, visible_bookings
from agenda.services import PUBLIC_FIELDS, SERVICE_FIELDS, BookingConflict, cancel_booking, review_booking, save_booking


class AgendaAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_access_agenda(request.user):
            raise PermissionDenied('Entre com uma conta ativa para acessar a agenda.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return visible_bookings(self.request.user)


class AdminAgendaAccessMixin(AgendaAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_business_admin(request.user):
            raise PermissionDenied('Somente administradores do laboratório podem gerenciar a agenda.')
        return super().dispatch(request, *args, **kwargs)


class BookingListView(AgendaAccessMixin, ListView):
    template_name = 'agenda/list.html'
    paginate_by = 25

    def get_default_month(self):
        return timezone.localdate().strftime('%Y-%m') if is_business_admin(self.request.user) else ''

    def get_default_situation(self):
        return ''

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as error:
            return render(request, 'agenda/error.html', {'message': ' '.join(error.messages)}, status=400)

    def get_queryset(self):
        self.month = self.request.GET.get('mes', self.get_default_month())
        if self.month:
            month_bounds(self.month)
        self.calendar_month = self.month or timezone.localdate().strftime('%Y-%m')
        self.situation = self.request.GET.get('situacao', self.get_default_situation())
        self.category = self.request.GET.get('categoria', '')
        self.query = self.request.GET.get('q', '').strip()[:150]
        queryset = filter_bookings(super().get_queryset(), month=self.month, category=self.category, situation=self.situation)
        if self.query:
            queryset = queryset.filter(Q(requerente__icontains=self.query) | Q(motivo__icontains=self.query)
                | Q(servico__nome__icontains=self.query) | Q(equipamento__nome__icontains=self.query)
                | Q(espaco__nome__icontains=self.query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(month=self.month, selected_category=self.category, categories=CATEGORIES.items(),
                       calendar_month=self.calendar_month, selected_situation=self.situation,
                       situations=BOOKING_STATUSES.items(), query=self.query,
                       weeks=calendar_weeks(filter_bookings(self.object_list, month=self.calendar_month), self.calendar_month),
                       category_counts={name: self.object_list.filter(situacao='confirmado', **{name+'__isnull': False}).count()
                                        for name in CATEGORIES})
        return context


class BookingDetailView(AgendaAccessMixin, DetailView):
    model = Agendamento
    context_object_name = 'booking'
    template_name = 'agenda/detail.html'

    def get_context_data(self, **kwargs):
        creator = self.object.criado_por
        creator_name = (creator.get_full_name() or creator.username) if creator else (
            self.object.eventos.filter(acao='criar').values_list('ator_nome', flat=True).first() or 'Não registrado')
        return {**super().get_context_data(**kwargs), 'events': self.object.eventos.all()[:5], 'creator_name': creator_name}


@method_decorator(never_cache, name='dispatch')
class BookingCreatorPhotoView(AgendaAccessMixin, View):
    def get(self, request, pk):
        booking = get_object_or_404(self.get_queryset(), pk=pk)
        if not booking.criado_por or not booking.criado_por.foto:
            raise Http404
        try:
            stream = booking.criado_por.foto.open('rb')
        except OSError as error:
            raise Http404 from error
        response = FileResponse(stream, content_type='image/webp')
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class BookingWriteView(AgendaAccessMixin, View):
    def get_booking(self):
        if 'pk' in self.kwargs and not is_business_admin(self.request.user):
            raise PermissionDenied('Somente administradores do laboratório podem editar agendamentos.')
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['pk']) if 'pk' in self.kwargs else None

    def get(self, request, **kwargs):
        booking = self.get_booking()
        form = BookingForm(booking=booking, actor=request.user,
                           initial={'categoria': request.GET['categoria']} if 'categoria' in request.GET else {})
        return render(request, 'agenda/form.html', {'form': form, 'booking': booking})

    def post(self, request, **kwargs):
        booking = self.get_booking()
        if request.POST.get('atualizar') == '1':
            # POST keeps names, reasons and CSRF tokens out of URL/history/logs.
            initial = {key: request.POST[key] for key in PUBLIC_FIELDS if key in request.POST}
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
            return render(request, 'agenda/form.html', {'form': form, 'booking': booking})
        form = BookingForm(request.POST, booking=booking, actor=request.user)
        response_status = 200
        if form.is_valid():
            try:
                saved = save_booking(actor=request.user,
                                     data={key: value for key, value in form.cleaned_data.items() if key in PUBLIC_FIELDS},
                                     booking_id=booking.pk if booking else None, expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                form.add_error(None, str(error))
                response_status = 409
            except ValidationError as error:
                for field, errors in error.message_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                messages.success(request, 'Solicitação enviada. Aguarde a confirmação de um administrador.'
                                 if saved.situacao == 'pendente' else 'Agendamento salvo.')
                return redirect('agenda:detail', pk=saved.pk)
        return render(request, 'agenda/form.html', {'form': form, 'booking': booking}, status=response_status)


class BookingCancelView(AdminAgendaAccessMixin, View):
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


class BookingReviewListView(AdminAgendaAccessMixin, BookingListView):
    template_name = 'agenda/requests.html'

    def get_queryset(self):
        return super().get_queryset().filter(Q(situacao__in=['pendente', 'rejeitado']) | Q(avaliado_em__isnull=False))

    def get_default_month(self):
        return ''

    def get_default_situation(self):
        return 'pendente'


class BookingReviewView(AdminAgendaAccessMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(self.get_queryset(), pk=pk)
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return render(request, 'agenda/error.html', {'message': 'Confira a decisão, a versão e os campos enviados.',
                                                       'booking': booking}, status=400)
        try:
            review_booking(actor=request.user, booking_id=pk, expected_version=form.cleaned_data['versao'],
                           decision=form.cleaned_data['decisao'])
        except BookingConflict as error:
            return render(request, 'agenda/error.html', {'message': str(error), 'booking': booking}, status=409)
        except ValidationError as error:
            return render(request, 'agenda/error.html', {'message': ' '.join(error.messages), 'booking': booking}, status=400)
        messages.success(request, 'Solicitação aceita. Horário reservado.' if form.cleaned_data['decisao'] == 'aprovar'
                         else 'Solicitação rejeitada.')
        return redirect('agenda:requests')
