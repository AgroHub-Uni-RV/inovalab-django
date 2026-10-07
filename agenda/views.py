from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from accounts.policies import is_business_admin
from agenda.forms import BookingForm, CancelForm, ReviewForm
from agenda.models import BOOKING_STATUSES, CATEGORIES
from agenda.policies import can_access_agenda
from agenda.selectors import calendar_weeks, filter_bookings, month_bounds, visible_bookings, visible_booking
from agenda.services import PUBLIC_FIELDS, SERVICE_FIELDS, BookingConflict, cancel_booking, review_booking, save_booking
from accounts.photos import profile_photo_response
from accounts.agrohub.client import AgroHubError
from agenda.remote_requests import decide_reservation, reservations


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
        remote, self.visits_unavailable = confirmed_visits(self.request)
        queryset = filter_bookings(sorted(super().get_queryset() + remote, key=lambda row: (row.inicio, row.categoria, row.pk)), month=self.month, category=self.category, situation=self.situation)
        if self.query:
            queryset = [row for row in queryset if self.query.casefold() in ' '.join((
                row.criador_nome, getattr(getattr(row, 'criado_por', None), 'username', ''),
                row.objeto_nome, row.motivo, getattr(row, 'sala', ''),
            )).casefold()]
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(month=self.month, selected_category=self.category, categories=CATEGORIES.items(),
                       calendar_month=self.calendar_month, selected_situation=self.situation,
                       situations=BOOKING_STATUSES.items(), query=self.query,
                       weeks=calendar_weeks(filter_bookings(self.object_list, month=self.calendar_month), self.calendar_month),
                       visits_unavailable=self.visits_unavailable,
                       category_counts={name: sum(row.situacao == 'confirmado' and row.categoria == name for row in self.object_list)
                                        for name in CATEGORIES})
        if self.visits_unavailable:
            context['category_counts']['visita'] = None
        return context


class BookingDetailView(AgendaAccessMixin, DetailView):
    context_object_name = 'booking'
    template_name = 'agenda/detail.html'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'events': self.object.eventos.all()[:5],
                'creator_name': self.object.criador_nome}


@method_decorator(never_cache, name='dispatch')
class BookingCreatorPhotoView(AgendaAccessMixin, View):
    def get(self, request, pk, category):
        booking = self.get_object()
        if not booking.criado_por or not booking.criado_por.tem_foto:
            raise Http404
        return profile_photo_response(booking.criado_por)


class BookingWriteView(AgendaAccessMixin, View):
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
                return render(request, 'agenda/choose_category.html', {
                    'category_error': 'Selecione uma das formas de agendamento abaixo.' if category else '',
                }, status=400 if category else 200)
        form = BookingForm(booking=booking, actor=request.user,
                           initial={'categoria': request.GET['categoria']} if booking is None else {})
        return render(request, 'agenda/form.html', {'form': form, 'booking': booking})

    def post(self, request, **kwargs):
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
            return render(request, 'agenda/form.html', {'form': form, 'booking': booking})
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
                messages.success(request, 'Solicitação enviada. Aguarde a confirmação de um administrador.'
                                 if saved.situacao == 'pendente' else 'Agendamento salvo.')
                return redirect(saved)
        return render(request, 'agenda/form.html', {'form': form, 'booking': booking}, status=response_status)


class BookingCancelView(AdminAgendaAccessMixin, View):
    def get(self, request, pk, category):
        booking = self.get_object()
        return render(request, 'agenda/cancel.html', {'booking': booking, 'form': CancelForm(initial={'versao': booking.versao})})

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
                return redirect('agenda:list')
        return render(request, 'agenda/error.html', {'message': message, 'booking': booking}, status=response_status)


class BookingHistoryView(AgendaAccessMixin, ListView):
    template_name = 'agenda/history.html'
    paginate_by = 25

    def get_queryset(self):
        self.booking = self.get_object()
        return self.booking.eventos.all()

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'booking': self.booking}


@method_decorator(never_cache, name='dispatch')
class BookingReviewListView(AdminAgendaAccessMixin, ListView):
    template_name = 'agenda/requests.html'
    paginate_by = 25
    http_method_names = ['get', 'head', 'options']

    def get(self, request, *args, **kwargs):
        try:
            response = super().get(request, *args, **kwargs)
        except ValidationError as error:
            return render(request, 'agenda/error.html', {'message': ' '.join(error.messages)}, status=400)
        response.status_code = self.provider_status
        return response

    def get_queryset(self):
        self.query = self.request.GET.get('q', '').strip()[:150]
        self.month = self.request.GET.get('mes', '')
        self.selected_status = self.request.GET.get('status', '')
        if self.selected_status not in ('', 'pendente', 'cancelada', 'recusada'):
            self.selected_status = ''
        self.reservations = []
        if self.month:
            month_bounds(self.month)
        self.provider_status, self.provider_error = 200, ''
        if self.request.user.agrohub_id is None:
            self.provider_error = 'Entre com uma conta administrativa vinculada ao AgroHub para consultar as reservas.'
            return []
        try:
            rows = reservations(self.request)
            self.reservations = [row for row in rows if row.status != 'confirmada'
                and (not self.month or timezone.localtime(row.inicio).strftime('%Y-%m') == self.month)
                and (not self.query or self.query.casefold() in ' '.join((str(row.id), row.sala, row.titulo, row.solicitante)).casefold())]
            return [row for row in self.reservations if not self.selected_status or row.status == self.selected_status]
        except (BookingConflict, ValidationError):
            self.provider_status = 503
            self.provider_error = 'Não foi possível registrar as reservas confirmadas na agenda. Atualize as solicitações.'
            return []
        except AgroHubError as error:
            self.provider_status = 403 if error.status in (401, 403) else 503
            self.provider_error = ('Sua sessão não tem permissão para consultar as reservas no AgroHub. Entre novamente com uma conta autorizada.'
                                   if self.provider_status == 403 else
                                   'Não foi possível consultar as solicitações no AgroHub. Tente atualizar a página em instantes.')
            return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        columns = [
            {'status': status, 'label': label, 'tone': tone,
             'count': sum(row.status == status for row in self.reservations),
             'bookings': [row for row in context['object_list'] if row.status == status]}
            for status, label, tone in (
                ('pendente', 'Pendentes', 'criacao'),
                ('cancelada', 'Canceladas', 'avaliacao'), ('recusada', 'Recusadas', 'avaliacao'))
        ]
        return {**context, 'query': self.query, 'month': self.month, 'selected_status': self.selected_status,
                'provider_error': self.provider_error, 'columns': columns,
                'stat_counts': {'all': len(self.reservations),
                                **{column['status']: column['count'] for column in columns}}}

    def paginate_queryset(self, queryset, page_size):
        if self.provider_error:
            paginator = self.get_paginator([], page_size)
            return paginator, paginator.page(1), [], False
        return super().paginate_queryset(queryset, page_size)


@method_decorator(never_cache, name='dispatch')
class RemoteBookingDecisionView(AdminAgendaAccessMixin, View):
    http_method_names = ['post', 'options']

    def post(self, request, pk):
        decision = request.POST.get('decisao')
        allowed = {'csrfmiddlewaretoken', 'decisao', 'q', 'mes', 'status'}
        if (decision not in ('confirmar', 'cancelar', 'recusar') or set(request.POST) - allowed
                or any(len(request.POST.getlist(key)) != 1 for key in request.POST)
                or request.POST.get('status', '') not in ('', 'pendente', 'cancelada', 'recusada')):
            return self.error(request, 'Confira a ação e os campos enviados.', 400)
        if request.user.agrohub_id is None:
            return self.error(request, 'Entre com uma conta administrativa vinculada ao AgroHub.', 403)
        month = request.POST.get('mes', '')
        try:
            if month:
                month_bounds(month)
            remote = decide_reservation(request, pk, decision)
        except ValidationError:
            return self.error(request, 'Confira o mês e atualize a agenda para verificar o resultado no AgroHub.', 400)
        except BookingConflict:
            return self.error(request, 'A agenda está sendo atualizada. Confira as solicitações antes de tentar novamente.', 503)
        except AgroHubError as error:
            status = error.status
            if status in (401, 403):
                return self.error(request, 'Sua conta não tem permissão para alterar esta reserva no AgroHub.', 403)
            if status == 404:
                return self.error(request, 'A reserva não está mais disponível no AgroHub.', 404)
            if status == 409:
                return self.error(request, 'A reserva não está mais pendente. Atualize as solicitações.', 409)
            if status in (400, 422):
                return self.error(request, 'O AgroHub recusou a operação. Confira a situação e o horário da reserva.', 400)
            return self.error(request, 'Não foi possível confirmar o resultado no AgroHub. Atualize as solicitações antes de tentar novamente.', 503)
        messages.success(request, f'Reserva #{pk} confirmada no AgroHub. Disponível na agenda de visitas.' if decision == 'confirmar'
                         else f'Reserva #{pk} recusada no AgroHub.' if decision == 'recusar'
                         else f'Reserva #{pk} cancelada no AgroHub.')
        params = {key: request.POST.get(key, '').strip()[:150] for key in ('q', 'mes', 'status') if request.POST.get(key)}
        return redirect(reverse('agenda:requests') + ('?'+urlencode(params) if params else ''))

    def error(self, request, message, status):
        return render(request, 'agenda/error.html', {'message': message, 'remote_request': True}, status=status)


class BookingReviewView(AdminAgendaAccessMixin, View):
    def post(self, request, pk, category):
        booking = self.get_object()
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return render(request, 'agenda/error.html', {'message': 'Confira a decisão, a versão e os campos enviados.',
                                                       'booking': booking}, status=400)
        try:
            saved = review_booking(actor=request.user, category=category, booking_id=pk, expected_version=form.cleaned_data['versao'],
                           decision=form.cleaned_data['decisao'])
        except BookingConflict as error:
            return render(request, 'agenda/error.html', {'message': str(error), 'booking': booking}, status=409)
        except ValidationError as error:
            return render(request, 'agenda/error.html', {'message': ' '.join(error.messages), 'booking': booking}, status=400)
        messages.success(request, 'Solicitação aceita. Horário reservado.' if form.cleaned_data['decisao'] == 'aprovar'
                         else 'Solicitação rejeitada.')
        return redirect('agenda:requests')


def confirmed_visits(request):
    if request.user.agrohub_id is None:
        return [], True
    try:
        return [row for row in reservations(request) if row.status == 'confirmada'], False
    except AgroHubError:
        return [], True
