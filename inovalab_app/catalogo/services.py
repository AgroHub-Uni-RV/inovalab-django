from collections.abc import Mapping

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.catalogo.models import Equipamento


PUBLIC_FIELDS = {
    Equipamento: ('nome', 'descricao', 'foto', 'status'),
}


@transaction.atomic
def save_entry(*, actor, model, data: Mapping, instance=None):
    """Authorize, validate and persist public catalog fields for web and API."""
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem manter o catálogo.')
    if model is not Equipamento:
        raise ValidationError('Serviços são definidos por solicitação de agendamento.')
    unknown = set(data) - set(PUBLIC_FIELDS[model])
    if unknown:
        raise ValidationError({field: 'Este campo não pode ser alterado.' for field in unknown})
    if instance is not None and not isinstance(instance, model):
        raise ValueError('O cadastro não pertence ao modelo informado.')
    entry = get_object_or_404(model.objects.select_for_update(), pk=instance.pk, excluido_em__isnull=True) if instance is not None else model()
    for field, value in data.items():
        if model is Equipamento and field == 'foto':
            entry._meta.get_field('foto').save_form_data(entry, value)
        else:
            setattr(entry, field, value)
    if isinstance(entry.nome, str):
        entry.nome = entry.nome.strip()
    entry.full_clean()
    entry.save()
    return entry


@transaction.atomic
def delete_equipment(*, actor, equipment_id):
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem excluir equipamentos.')
    equipment = get_object_or_404(Equipamento.objects.select_for_update(), pk=equipment_id)
    if equipment.excluido_em is None:
        equipment.excluido_em = timezone.now()
        equipment.save(update_fields=['excluido_em'])
    return equipment
