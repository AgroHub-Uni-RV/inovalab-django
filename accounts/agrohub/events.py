from hashlib import sha256
from time import monotonic
from urllib.parse import urljoin, urlsplit

from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.agrohub.client import AgroHubClient, AgroHubError, base_url, safe_picture_url

MAX_PAGES = 20
FETCH_BUDGET_SECONDS = 5
CACHE_SECONDS = 300
CATEGORIES = {'mentoria': 'MENTORIA', 'workshop': 'WORKSHOP', 'pitch': 'PITCH',
              'capacitacao': 'CAPACITAÇÃO', 'outro': 'OUTRO'}


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _detail_url(value):
    value = _text(value, 2048)
    if not value or any(ord(char) < 32 for char in value) or '\\' in value:
        return ''
    try:
        origin = urlsplit(base_url())
        target = urljoin(f'{origin.scheme}://{origin.netloc}/', value)
        parsed = urlsplit(target)
        if not parsed.hostname or parsed.username or parsed.password:
            return ''
        if parsed.scheme == 'https' or (parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc):
            return target
    except ValueError:
        pass
    return ''


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
    category = row.get('category')
    if not isinstance(category, str) or category not in CATEGORIES:
        category = 'outro'
    return {'id': row['id'], 'title': title[:200], 'start': start, 'end': end,
            'summary': _text(row.get('summary'), 500) or _text(row.get('description'), 10000),
            'category': category, 'category_label': CATEGORIES[category],
            'image_url': safe_picture_url(row.get('image')),
            'location': _text(row.get('location'), 255), 'detail_url': _detail_url(row.get('detail_url'))}


def load_events():
    key = 'agrohub.calendar.events.v2.'+sha256(base_url().encode()).hexdigest()
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
