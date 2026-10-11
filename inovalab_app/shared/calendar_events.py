"""Local dates covered by the host's normalized calendar events."""
from datetime import timedelta

from django.utils import timezone


def event_days_in_period(events, first, last):
    """Map titles to days in [first, last), excluding a midnight end."""
    days = {}
    for event in events:
        begin, end = event['start'], event['end'] or event['start']
        if begin >= last or end < first:
            continue
        day = timezone.localtime(max(begin, first)).date()
        final = timezone.localtime(min(max(begin, end - timedelta(microseconds=1)),
                                       last - timedelta(microseconds=1))).date()
        while day <= final:
            days.setdefault(day, []).append(event['title'])
            day += timedelta(days=1)
    return days
