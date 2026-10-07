"""Exportação privada, atômica e explícita dos dados sem destino operacional."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder


def archive_legacy(payload, *, database):
    if not payload['bookings'] and not payload['remote_links']:
        return None
    configured = getattr(settings, 'AGENDAS_LEGACY_ARCHIVE_DIR', '') or os.environ.get('AGENDAS_LEGACY_ARCHIVE_DIR')
    if not configured and not settings.DEBUG:
        raise RuntimeError('Defina AGENDAS_LEGACY_ARCHIVE_DIR em armazenamento privado durável antes de migrar o legado.')
    directory = Path(configured) if configured else Path(settings.BASE_DIR) / '.private' / 'agenda-legacy'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    identity = hashlib.sha256(str(database).encode()).hexdigest()[:16]
    destination = directory / f'agenda-{identity}-{uuid4().hex}.json'
    descriptor, temporary = tempfile.mkstemp(prefix='.agenda-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'schema': 1, **payload}, stream, cls=DjangoJSONEncoder, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return destination
