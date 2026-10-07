import calendar
import re
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.policies import is_business_admin
from agenda.models import BOOKING_MODELS, EventoAgendamento
from agenda.models import BOOKING_STATUSES, CATEGORIES
from agenda.policies import can_access_agenda, can_view_own_bookings


def _visible_queryset(actor, category, *, personal=False):
    model = BOOKING_MODELS[category]
    if not (can_view_own_bookings(actor) if personal else can_access_agenda(actor)):
        return model.objects.none()
    related = [category, 'criado_por', 'avaliado_por']
    if category == 'servico':
        related.append('material_gasto')
    query = model.objects.all().select_related(*related).prefetch_related(
        Prefetch('eventos', queryset=EventoAgendamento.objects.filter(acao='criar'), to_attr='eventos_de_criacao'))
    if category == 'servico':
        query = query.prefetch_related('equipamentos')
    if not personal:
        query = query.filter(cancelado_em__isnull=True)
    if personal or not is_business_admin(actor):
        query = query.filter(criado_por=actor)
    return query


def visible_bookings(actor):
    rows = []
    for category in BOOKING_MODELS:
        rows.extend(_visible_queryset(actor, category))
    return sorted(rows, key=lambda row: (row.inicio, row.categoria, row.pk))


def visible_booking(actor, category, pk):
    if category not in BOOKING_MODELS:
        raise Http404
    return get_object_or_404(_visible_queryset(actor, category), pk=pk)


def own_bookings(actor):
    return [row for category in BOOKING_MODELS for row in _visible_queryset(actor, category, personal=True)]


def own_booking(actor, category, pk):
    if category not in BOOKING_MODELS:
        raise Http404
    return get_object_or_404(_visible_queryset(actor, category, personal=True), pk=pk)


def month_bounds(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}', value):
        raise ValidationError({'mes': 'Informe o mês no formato AAAA-MM.'})
    year, month = map(int, value.split('-'))
    try:
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    except ValueError as error:
        raise ValidationError({'mes': 'Informe um mês válido.'}) from error
    return timezone.make_aware(start), timezone.make_aware(end)


def filter_bookings(queryset, *, month=None, category=None, situation=None):
    if situation:
        if situation not in BOOKING_STATUSES:
            raise ValidationError({'situacao': 'Selecione uma situação válida.'})
        queryset = [row for row in queryset if row.situacao == situation]
    if category:
        if category not in CATEGORIES:
            raise ValidationError({'categoria': 'Selecione uma categoria válida.'})
        queryset = [row for row in queryset if row.categoria == category]
    if month:
        start, end = month_bounds(month)
        queryset = [row for row in queryset if row.inicio < end and row.fim > start]
    return queryset


def calendar_weeks(queryset, month):
    start, end = month_bounds(month)
    # Count from the entire filtered month, independently of table pagination.
    counts, previews = {}, {}
    for booking in queryset:
        if booking.situacao != 'confirmado' or booking.cancelado_em is not None:
            continue
        first, last = booking.inicio, booking.fim
        first, last = max(first, start), min(last, end)
        day = timezone.localtime(first).date()
        final_day = timezone.localtime(last - timedelta(microseconds=1)).date()
        while day <= final_day:
            counts[day] = counts.get(day, 0) + 1
            items = previews.setdefault(day, [])
            if len(items) < 3:
                items.append(booking)
            day += timedelta(days=1)
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(start.year, start.month)
    return [[{'date': day, 'in_month': day.month == start.month, 'count': counts.get(day, 0),
              'bookings': previews.get(day, []), 'sunday': day.weekday() == 6}
             for day in week] for week in weeks]
