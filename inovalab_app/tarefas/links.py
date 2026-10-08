"""Normalize, validate and persist the task's team and optional resources."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import F

from inovalab_app.catalogo.models import Equipamento
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.models import TarefaEquipamento, TarefaMaterial, TarefaResponsavel


LINK_FIELDS = {'responsaveis', 'equipamentos', 'materiais_gastos'}
LEGACY_LINK_FIELDS = {'responsavel', 'equipamento', 'material_gasto', 'quantidade_material_gasto'}


def link_snapshot(task):
    if not task.pk:
        return {'responsaveis': [], 'equipamentos': [], 'materiais_gastos': []}
    return {
        'responsaveis': sorted(user.pk for user in task.responsaveis.all()),
        'equipamentos': sorted(equipment.pk for equipment in task.equipamentos.all()),
        'materiais_gastos': sorted(
            [{'material': entry.material_id, 'quantidade': entry.quantidade} for entry in task.materiais_gastos.all()],
            key=lambda entry: entry['material']),
    }


def _objects(value, model, field, required=False):
    if not isinstance(value, (list, tuple)):
        raise ValidationError({field: 'Informe uma lista de cadastros.'})
    if required and not value:
        raise ValidationError({field: 'Selecione pelo menos um responsável.'})
    if any(not isinstance(item, model) or item.pk is None for item in value):
        raise ValidationError({field: 'Selecione cadastros válidos.'})
    if len({item.pk for item in value}) != len(value):
        raise ValidationError({field: 'Não repita o mesmo cadastro.'})
    return sorted(value, key=lambda item: item.pk)


def normalize_links(task, data):
    for plural, aliases in (
        ('responsaveis', {'responsavel'}), ('equipamentos', {'equipamento'}),
        ('materiais_gastos', {'material_gasto', 'quantidade_material_gasto'}),
    ):
        if plural in data and aliases & set(data):
            raise ValidationError({plural: 'Use somente a seleção múltipla ou o campo anterior.'})
    current_users = list(task.responsaveis.all()) if task.pk else []
    current_equipment = list(task.equipamentos.all()) if task.pk else []
    current_material = [{'material': entry.material, 'quantidade': entry.quantidade}
                        for entry in task.materiais_gastos.select_related('material')] if task.pk else []
    for plural, aliases, current in (
        ('responsaveis', {'responsavel'}, current_users),
        ('equipamentos', {'equipamento'}, current_equipment),
        ('materiais_gastos', {'material_gasto', 'quantidade_material_gasto'}, current_material),
    ):
        if len(current) > 1 and aliases & set(data):
            raise ValidationError({plural: 'Esta tarefa tem múltiplos vínculos. Use a seleção múltipla para alterá-los.'})
    users = data.get('responsaveis', [data['responsavel']] if 'responsavel' in data else current_users)
    equipment = data.get('equipamentos', [data['equipamento']] if data.get('equipamento') is not None
                         else [] if 'equipamento' in data else current_equipment)
    materials = data.get('materiais_gastos', current_material)
    if {'material_gasto', 'quantidade_material_gasto'} & set(data):
        material = data.get('material_gasto', task.material_gasto if task.pk else None)
        quantity = data.get('quantidade_material_gasto', task.quantidade_material_gasto if task.pk else '')
        if material is None and quantity:
            raise ValidationError({'material_gasto': 'Selecione o material da quantidade informada.'})
        materials = [{'material': material, 'quantidade': quantity}] if material is not None else []
    users = _objects(users, get_user_model(), 'responsaveis', required=True)
    equipment = _objects(equipment, Equipamento, 'equipamentos')
    if not isinstance(materials, (list, tuple)):
        raise ValidationError({'materiais_gastos': 'Informe uma lista de materiais e quantidades.'})
    normalized = []
    for entry in materials:
        if not isinstance(entry, dict) or set(entry) - {'material', 'quantidade'} or 'material' not in entry:
            raise ValidationError({'materiais_gastos': 'Informe material e quantidade por linha.'})
        quantity = entry.get('quantidade', '')
        if not isinstance(quantity, str) or len(quantity.strip()) > 150:
            raise ValidationError({'materiais_gastos': 'A quantidade deve ser um texto de até 150 caracteres.'})
        normalized.append({'material': entry['material'], 'quantidade': quantity.strip()})
    ordered_materials = _objects([entry['material'] for entry in normalized], Material, 'materiais_gastos')
    quantities = {entry['material'].pk: entry['quantidade'] for entry in normalized}
    return {'responsaveis': users, 'equipamentos': equipment,
            'materiais_gastos': [{'material': item, 'quantidade': quantities[item.pk]} for item in ordered_materials]}


def lock_and_validate_links(links, before):
    groups = (
        ('responsaveis', get_user_model(), 'is_active', {'is_active': True}, links['responsaveis']),
        ('equipamentos', Equipamento, 'status', {'excluido_em__isnull': True}, links['equipamentos']),
        ('materiais_gastos', Material, 'quantidade', {'status': 'disponivel'},
         [entry['material'] for entry in links['materiais_gastos']]),
    )
    for field, model, lock_field, criteria, resources in groups:
        previous = before.get(field, [])
        previous_ids = {entry['material'] for entry in previous} if field == 'materiais_gastos' else set(previous)
        for resource in resources:
            if not model.objects.filter(pk=resource.pk).update(**{lock_field: F(lock_field)}):
                raise ValidationError({field: 'Selecione cadastros válidos.'})
            if resource.pk not in previous_ids and not model.objects.filter(pk=resource.pk, **criteria).exists():
                raise ValidationError({field: 'Selecione cadastros ativos e disponíveis.'})


def apply_legacy_aliases(task, links, data):
    task.responsavel = links['responsaveis'][0]
    task.equipamento = links['equipamentos'][0] if links['equipamentos'] else None
    first = links['materiais_gastos'][0] if links['materiais_gastos'] else None
    task.material_gasto = first['material'] if first else None
    if first or {'materiais_gastos', 'material_gasto', 'quantidade_material_gasto'} & set(data):
        task.quantidade_material_gasto = first['quantidade'] if first else ''


def persist_links(task, links):
    for field, model, fk in (('responsaveis', TarefaResponsavel, 'responsavel'),
                             ('equipamentos', TarefaEquipamento, 'equipamento')):
        ids = [item.pk for item in links[field]]
        model.objects.filter(tarefa=task).exclude(**{fk+'_id__in': ids}).delete()
        existing = set(model.objects.filter(tarefa=task).values_list(fk+'_id', flat=True))
        model.objects.bulk_create([model(tarefa=task, **{fk+'_id': pk}) for pk in ids if pk not in existing])
    entries = links['materiais_gastos']
    TarefaMaterial.objects.filter(tarefa=task).exclude(material_id__in=[entry['material'].pk for entry in entries]).delete()
    for entry in entries:
        TarefaMaterial.objects.update_or_create(tarefa=task, material=entry['material'],
                                               defaults={'quantidade': entry['quantidade']})
    task._prefetched_objects_cache = {}
