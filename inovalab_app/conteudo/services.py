from datetime import datetime, timezone as dt_timezone
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.conteudo.models import Banner
from inovalab_app.conteudo.uploads import validated_image


PUBLIC_FIELDS = ('titulo', 'texto_alternativo', 'status', 'local', 'ordem', 'inicio_exibicao', 'fim_exibicao')


class BannerConflict(Exception):
    """The banner changed after the caller read it."""


def _require_admin(actor):
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem administrar banners.')


def _load(banner_id, expected_version):
    banner = get_object_or_404(Banner, pk=banner_id, excluido_em__isnull=True)
    if type(expected_version) is not int or not 1 <= expected_version <= 9223372036854775806:
        raise ValidationError({'versao': 'Informe a versão inteira positiva do banner.'})
    if banner.versao != expected_version:
        raise BannerConflict('O banner foi alterado. Atualize a página antes de tentar novamente.')
    return banner


def save_banner(*, actor, data, banner_id=None, expected_version=None, image=None):
    _require_admin(actor)
    unknown = set(data) - set(PUBLIC_FIELDS)
    if unknown:
        raise ValidationError({name: 'Este campo não pode ser alterado.' for name in unknown})
    banner = _load(banner_id, expected_version) if banner_id is not None else Banner()
    for name, value in data.items():
        if name == 'ordem' and type(value) is not int:
            raise ValidationError({'ordem': 'Informe uma ordem inteira não negativa.'})
        if name in ('inicio_exibicao', 'fim_exibicao') and value is not None:
            if not isinstance(value, datetime) or timezone.is_naive(value):
                raise ValidationError({name: 'Informe data e hora com fuso.'})
            value = value.astimezone(dt_timezone.utc)
        setattr(banner, name, value)
    if banner_id is None and image is None:
        raise ValidationError({'banner_img': 'Envie uma imagem WebP.'})
    if banner_id is not None:
        banner.versao = expected_version + 1
    banner.full_clean(exclude=['banner_img'])
    content = validated_image(image) if image is not None else None
    new_name = None
    storage = banner.banner_img.storage
    try:
        if content is not None:
            new_name = storage.save(f'banners/{uuid4().hex}.webp', content)
            banner.banner_img = new_name
        if banner_id is None:
            banner.save()
        else:
            values = {name: getattr(banner, name) for name in PUBLIC_FIELDS}
            values.update(banner_img=banner.banner_img.name, versao=banner.versao)
            changed = Banner.objects.filter(pk=banner.pk, versao=expected_version, excluido_em__isnull=True).update(**values)
            if not changed:
                raise BannerConflict('O banner foi alterado. Atualize a página antes de tentar novamente.')
    except Exception:
        if new_name is not None:
            storage.delete(new_name)
        raise
    return banner


def delete_banner(*, actor, banner_id, expected_version):
    _require_admin(actor)
    banner = _load(banner_id, expected_version)
    changed = Banner.objects.filter(pk=banner.pk, versao=expected_version, excluido_em__isnull=True).update(
        excluido_em=timezone.now(), versao=expected_version + 1,
    )
    if not changed:
        raise BannerConflict('O banner foi alterado. Atualize a página antes de tentar novamente.')
