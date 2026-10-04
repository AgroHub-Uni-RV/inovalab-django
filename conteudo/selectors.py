from django.db.models import Q
from django.utils import timezone

from accounts.policies import is_business_admin
from conteudo.models import Banner


def visible_banners(actor):
    return Banner.objects.filter(excluido_em__isnull=True) if is_business_admin(actor) else Banner.objects.none()


def published_banners(local, at=None):
    now = at if at is not None else timezone.now()
    return Banner.objects.filter(local=local, excluido_em__isnull=True).filter(
        Q(status='ativo') | Q(status='agendado', inicio_exibicao__lte=now, fim_exibicao__gt=now)
    )
