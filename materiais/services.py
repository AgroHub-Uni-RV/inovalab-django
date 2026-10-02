from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from accounts.policies import is_business_admin
from materiais.models import Material


PUBLIC_FIELDS = ('nome', 'categoria', 'quantidade', 'unidade', 'status', 'fonte')


class MaterialConflict(Exception):
    """A correction cannot overwrite a newer version of the material."""


def save_material(*, actor, data, material_id=None, expected_version=None):
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem manter materiais.')
    unknown = set(data) - set(PUBLIC_FIELDS)
    if unknown:
        raise ValidationError({field: 'Este campo não pode ser alterado.' for field in unknown})
    material = get_object_or_404(Material, pk=material_id) if material_id is not None else Material()
    if material_id is not None:
        if type(expected_version) is not int or not 1 <= expected_version <= 9223372036854775806:
            raise ValidationError({'versao': 'Informe a versão inteira positiva do material.'})
        if material.versao != expected_version:
            raise MaterialConflict('O material foi alterado. Atualize a página antes de tentar novamente.')
        material.versao = expected_version + 1
    for field, value in data.items():
        setattr(material, field, value)
    material.full_clean()
    if material_id is None:
        material.save()
    else:
        # No read transaction is needed: one conditional UPDATE atomically chooses the winner.
        values = {field: getattr(material, field) for field in PUBLIC_FIELDS}
        changed = Material.objects.filter(pk=material.pk, versao=expected_version).update(
            **values, versao=material.versao,
        )
        if not changed:
            raise MaterialConflict('O material foi alterado. Atualize a página antes de tentar novamente.')
    return material
