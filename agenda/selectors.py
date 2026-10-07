import calendar
import re
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.utils import timezone

from accounts.policies import is_business_admin
from agenda.models import Agendamento, EventoAgendamento
from agenda.models import BOOKING_STATUSES, CATEGORIES
from agenda.policies import can_access_agenda


def visible_bookings(actor):
    queryset = Agendamento.objects.filter(cancelado_em__isnull=True).select_related(
        'servico', 'equipamento', 'criado_por', 'material_gasto', 'avaliado_por',
    ).prefetch_related(Prefetch('eventos', queryset=EventoAgendamento.objects.filter(acao='criar'),
                               to_attr='eventos_de_criacao'))
    if not can_access_agenda(actor):
        return queryset.none()
    return queryset if is_business_admin(actor) else queryset.filter(criado_por=actor)


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
        queryset = queryset.filter(situacao=situation)
    if category:
        if category not in CATEGORIES:
            raise ValidationError({'categoria': 'Selecione uma categoria válida.'})
        queryset = queryset.filter(**category_filter(category))
    if month:
        start, end = month_bounds(month)
        queryset = queryset.filter(inicio__lt=end, fim__gt=start)
    return queryset


def category_filter(category):
    return {'visita': True} if category == 'visita' else {category + '__isnull': False}


def calendar_weeks(queryset, month):
    start, end = month_bounds(month)
    # Count from the entire filtered month, independently of table pagination.
    counts, previews = {}, {}
    for booking in queryset.filter(situacao='confirmado', cancelado_em__isnull=True).iterator(chunk_size=100):
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
