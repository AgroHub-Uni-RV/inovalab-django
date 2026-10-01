from collections.abc import Mapping

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.policies import is_business_admin
from catalogo.models import Equipamento, Espaco, Servico


PUBLIC_FIELDS = {
    Servico: ('nome', 'descricao', 'status'),
    Equipamento: ('nome', 'descricao', 'status'),
    Espaco: ('nome', 'capacidade_maxima_de_pessoas', 'status'),
}


@transaction.atomic
def save_entry(*, actor, model, data: Mapping, instance=None):
    """Authorize, validate and persist public catalog fields for web and API."""
    if not is_business_admin(actor):
        raise PermissionDenied('Somente administradores do laboratório podem manter o catálogo.')
    unknown = set(data) - set(PUBLIC_FIELDS[model])
    if unknown:
        raise ValidationError({field: 'Este campo não pode ser alterado.' for field in unknown})
    if instance is not None and not isinstance(instance, model):
        raise ValueError('O cadastro não pertence ao modelo informado.')
    entry = model.objects.select_for_update().get(pk=instance.pk) if instance is not None else model()
    for field, value in data.items():
        setattr(entry, field, value)
    if isinstance(entry.nome, str):
        entry.nome = entry.nome.strip()
    entry.full_clean()
    entry.save()
    return entry
