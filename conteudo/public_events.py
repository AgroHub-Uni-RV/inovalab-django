from datetime import date, timedelta

from django.utils import timezone

from core.agrohub_events import load_events

MONTH_NAMES = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
               'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')
MONTH_ABBREVIATIONS = ('JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ')


def _clock(moment):
    return f'{moment.hour}h{moment.minute:02d}' if moment.minute else f'{moment.hour}h'


def _card(event):
    start = timezone.localtime(event['start'])
    end = timezone.localtime(event['end']) if event['end'] else None
    time_label = _clock(start)
    if end:
        end_label = _clock(end) if end.date() == start.date() else f'{end:%d/%m} {_clock(end)}'
        time_label += ' às '+end_label
    return {name: event[name] for name in ('id', 'title', 'summary', 'category', 'category_label',
                                          'image_url', 'location', 'detail_url')} | {
        'day': start.day, 'month_abbrev': MONTH_ABBREVIATIONS[start.month-1],
        'date_iso': start.date().isoformat(), 'time_label': time_label,
    }


def public_events_context():
    events, failed = load_events()
    today, now = timezone.localdate(), timezone.now()
    ordered = sorted(events, key=lambda event: (event['start'], event['id']))
    upcoming = [event for event in ordered if timezone.localtime(event['start']).date() >= today
                or (event['end'] and event['end'] >= now)][:24]
    if len(upcoming) < 2:
        ids = {event['id'] for event in upcoming}
        recent = [event for event in ordered if event['id'] not in ids]
        upcoming += recent[-(24-len(upcoming)):]
    cards = [_card(event) for event in upcoming]
    event_dates = sorted({card['date_iso'] for card in cards})
    first = date(today.year, today.month, 1)
    grid_start = first-timedelta(days=(first.weekday()+1) % 7)
    cells = []
    for offset in range(42):
        day = grid_start+timedelta(days=offset)
        iso = day.isoformat()
        cells.append({'day': day.day, 'date_iso': iso, 'outside': day.month != today.month,
                      'has_event': iso in event_dates,
                      'label': f'{day.day} de {MONTH_NAMES[day.month-1]} de {day.year}'
                               + (' — eventos disponíveis' if iso in event_dates else '')})
    return {'event_cards': cards, 'event_dates': event_dates, 'events_failed': failed,
            'calendar_cells': cells, 'calendar_month_label': MONTH_NAMES[today.month-1],
            'calendar_initial_year': today.year, 'calendar_weekday_labels': ('D', 'S', 'T', 'Q', 'Q', 'S', 'S'),
            'events_calendar_payload': {'eventDates': event_dates, 'initialYear': today.year,
                                        'initialMonth': today.month, 'monthNames': MONTH_NAMES}}
