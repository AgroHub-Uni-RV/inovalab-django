from hashlib import sha256
from time import monotonic

from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.agrohub.client import AgroHubClient, AgroHubError, base_url

MAX_PAGES = 20
FETCH_BUDGET_SECONDS = 5
CACHE_SECONDS = 300


def _datetime(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = parse_datetime(value)
        if parsed is not None and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
    except ValueError:
        return None


def _event(row):
    if not isinstance(row, dict) or row.get('is_active') is not True or type(row.get('id')) is not int:
        return None
    start = _datetime(row.get('start_date'))
    end = _datetime(row['end_date']) if row.get('end_date') is not None else None
    title = row.get('title')
    if (start is None or not isinstance(title, str) or not title
            or (row.get('end_date') is not None and (end is None or end < start))):
        return None
    return {'id': row['id'], 'title': title[:200], 'start': start, 'end': end}


def load_events():
    key = 'agrohub.calendar.events.v1.'+sha256(base_url().encode()).hexdigest()
    saved = cache.get(key)
    if saved is not None:
        return saved, False
    client = AgroHubClient()
    events, seen = [], set()
    # Orçamento entre páginas; o transporte aplica timeout por operação de socket.
    next_page_deadline = monotonic()+FETCH_BUDGET_SECONDS
    try:
        for page in range(1, MAX_PAGES+1):
            remaining = next_page_deadline-monotonic()
            if remaining <= 0:
                raise AgroHubError()
            payload = client.events_page(page, timeout=remaining)
            rows, next_page = payload.get('results'), payload.get('next')
            if not isinstance(rows, list) or len(rows) > 100 or (next_page is not None and not isinstance(next_page, str)):
                raise AgroHubError()
            for row in rows:
                event = _event(row)
                if event is not None and event['id'] not in seen:
                    seen.add(event['id'])
                    events.append(event)
            if not next_page:
                cache.set(key, events, CACHE_SECONDS)
                return events, False
            # Não seguir URLs recebidas: manter rota/origem fixas e avançar a página.
        raise AgroHubError()
    except AgroHubError:
        return [], True
