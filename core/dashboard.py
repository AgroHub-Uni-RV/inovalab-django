import calendar
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.utils import timezone
from django.utils.dates import MONTHS

from accounts.policies import is_business_admin
from agenda.selectors import visible_bookings
from tarefas.selectors import visible_tasks

TASK_TABS = {'pendentes': ('Pendentes', ['demanda']),
             'andamento': ('Em andamento', ['criacao', 'avaliacao']),
             'concluidas': ('Concluídas', ['concluido'])}
BOOKING_TABS = {'semana': 'Essa semana', 'proximos': 'Próximos', 'concluidos': 'Concluídos'}


def _month_date(year, month, offset):
    index = year * 12 + month - 1 + offset
    return datetime(index // 12, index % 12 + 1, 1)


def _months(bookings, today):
    first = timezone.make_aware(_month_date(today.year, today.month, 0))
    last = timezone.make_aware(_month_date(today.year, today.month, 6))
    counts = {}
    for begin, end in bookings.filter(inicio__lt=last, fim__gt=first).values_list('inicio', 'fim').iterator():
        day = timezone.localtime(max(begin, first)).date()
        final = timezone.localtime(min(end, last)-timedelta(microseconds=1)).date()
        while day <= final:
            counts[day] = counts.get(day, 0) + 1
            day += timedelta(days=1)
    months = []
    for offset in range(6):
        date = _month_date(today.year, today.month, offset)
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(date.year, date.month)
        months.append({'year': date.year, 'month': date.month, 'name': MONTHS[date.month],
            'weeks': [[{'date': day, 'in_month': day.month == date.month, 'today': day == today,
                        'sunday': day.weekday() == 6, 'reservations': counts.get(day, 0)}
                       for day in week] for week in weeks]})
    return months


def dashboard_context(actor, *, now=None, task_tab='pendentes', booking_tab='semana'):
    now = now if now is not None else timezone.now()
    admin = is_business_admin(actor)
    task_tab = task_tab if task_tab in TASK_TABS else 'pendentes'
    booking_tab = booking_tab if booking_tab in BOOKING_TABS else 'semana'
    tasks = list(visible_tasks(actor).filter(status__in=TASK_TABS[task_tab][1])[:10])
    for task in tasks:
        task.overdue = bool(task.prazo and task.prazo < now and task.status != 'concluido')
    all_bookings = visible_bookings(actor).filter(situacao='confirmado')
    today = timezone.localdate(now)
    monday = today - timedelta(days=today.weekday())
    start = timezone.make_aware(datetime.combine(monday, datetime.min.time()))
    end = start + timedelta(days=7)
    if booking_tab == 'concluidos':
        bookings = all_bookings.filter(fim__lte=now).order_by('-fim', '-pk')
    elif booking_tab == 'proximos':
        bookings = all_bookings.filter(inicio__gte=end)
    else:
        bookings = all_bookings.filter(inicio__lt=end, fim__gt=max(start, now))
    return {
        'is_business_admin': admin, 'tasks': tasks, 'bookings': list(bookings[:10]) if admin else [],
        'task_tab': task_tab, 'booking_tab': booking_tab, 'months': _months(all_bookings, today),
        'weekday_labels': ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'],
        'task_tabs': [{'key': key, 'label': value[0], 'query': urlencode({'tarefas': key, 'agenda': booking_tab})}
                      for key, value in TASK_TABS.items()],
        'booking_tabs': [{'key': key, 'label': label, 'query': urlencode({'tarefas': task_tab, 'agenda': key})}
                         for key, label in BOOKING_TABS.items()],
    }
