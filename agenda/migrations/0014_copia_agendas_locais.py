import json
import os
from pathlib import Path
from django.conf import settings
from django.db import migrations, models
from django.core.management.color import no_style
from agenda.legacy_archive import archive_legacy


def copy_rows(apps, schema_editor):
    alias = schema_editor.connection.alias
    old = apps.get_model('agenda', 'Agendamento')
    event = apps.get_model('agenda', 'EventoAgendamento')
    receipt = apps.get_model('integracoes', 'PedidoIntegracao')
    remote = apps.get_model('agenda', 'ReservaAgroHub')
    excluded = list(old.objects.using(alias).filter(servico__isnull=True, equipamento__isnull=True).values_list('pk', flat=True))
    archive_legacy({
        'bookings': list(old.objects.using(alias).filter(pk__in=excluded).values()),
        'equipment_links': list(old.equipamentos.through.objects.using(alias).filter(agendamento_id__in=excluded).values()),
        'events': list(event.objects.using(alias).filter(agendamento_id__in=excluded).values()),
        'receipts': list(receipt.objects.using(alias).filter(agendamento_id__in=excluded).values()),
        'remote_links': list(remote.objects.using(alias).values()),
        'visit_locks': list(apps.get_model('agenda', 'ControleAgendaVisitas').objects.using(alias).values()),
        'local_booking_categories': {str(pk): category for category in ('servico', 'equipamento')
            for pk in old.objects.using(alias).filter(**{category + '__isnull': False}).values_list('pk', flat=True)},
    }, database=schema_editor.connection.settings_dict['NAME'])
    # PROTECT receipts must be archived and removed before deleting excluded bookings.
    receipt.objects.using(alias).filter(agendamento_id__in=excluded).delete()
    event.objects.using(alias).filter(agendamento_id__in=excluded).delete()
    for category, name in [('servico', 'AgendaServico'), ('equipamento', 'AgendaEquipamento')]:
        target = apps.get_model('agenda', name)
        fields = [field.attname for field in target._meta.concrete_fields]
        source = old.objects.using(alias).filter(**{category+'__isnull': False})
        expected = source.count()
        for row in source.iterator():
            values = {field: getattr(row, field) for field in fields}
            saved = target.objects.using(alias).create(**values)
            target.objects.using(alias).filter(pk=saved.pk).update(criado_em=row.criado_em)
            if category == 'servico':
                # Old and new models temporarily share a reverse related_name.
                # Read/write through tables directly to avoid descriptor collisions.
                ids = old.equipamentos.through.objects.using(alias).filter(agendamento_id=row.pk).values_list('equipamento_id', flat=True)
                target.equipamentos.through.objects.using(alias).bulk_create([
                    target.equipamentos.through(agendaservico_id=saved.pk, equipamento_id=pk) for pk in ids])
            event.objects.using(alias).filter(agendamento_id=row.pk).update(**{'agenda_'+category+'_id': row.pk})
            receipt.objects.using(alias).filter(agendamento_id=row.pk).update(**{'agenda_'+category+'_id': row.pk})
        if target.objects.using(alias).count() != expected:
            raise RuntimeError('Falha ao conferir cópia das agendas locais.')
    if event.objects.using(alias).filter(agenda_servico__isnull=True, agenda_equipamento__isnull=True).exists() or receipt.objects.using(alias).filter(agenda_servico__isnull=True, agenda_equipamento__isnull=True).exists():
        raise RuntimeError('Há eventos ou recibos sem agenda tipada.')
    for statement in schema_editor.connection.ops.sequence_reset_sql(no_style(), [apps.get_model('agenda', 'AgendaServico'), apps.get_model('agenda', 'AgendaEquipamento')]):
        schema_editor.execute(statement)


def restore_rows(apps, schema_editor):
    alias = schema_editor.connection.alias
    old = apps.get_model('agenda', 'Agendamento')
    event = apps.get_model('agenda', 'EventoAgendamento')
    receipt = apps.get_model('integracoes', 'PedidoIntegracao')
    archive_path = getattr(settings, 'AGENDAS_LEGACY_RESTORE_FILE', '') or os.environ.get('AGENDAS_LEGACY_RESTORE_FILE')
    payload = json.loads(Path(archive_path).read_text(encoding='utf-8')) if archive_path else None
    if payload is not None and payload.get('schema') != 1:
        raise RuntimeError('Arquivo de recuperação de agenda incompatível.')
    sources = [(category, apps.get_model('agenda', name)) for category, name in
               [('servico', 'AgendaServico'), ('equipamento', 'AgendaEquipamento')]]
    # Allocate every collision explicitly above all existing/source/archive IDs.
    # PostgreSQL sequences do not advance when inserting an explicit primary key.
    reserved = set(old.objects.using(alias).values_list('pk', flat=True))
    for category, source in sources:
        reserved.update(source.objects.using(alias).values_list('pk', flat=True))
    reserved.update(row['id'] for row in (payload or {}).get('bookings', []))
    next_id = max(reserved, default=0) + 1
    assigned = set()
    typed_mapping = {}
    legacy_mapping = {}

    def restore_booking(values, category=None):
        nonlocal next_id
        original = values.pop('id')
        existing = old.objects.using(alias).filter(pk=original).first()
        same_target = existing is None or (
            category is not None and getattr(existing, category + '_id') is not None
        ) or (category is None and existing.servico_id is None and existing.equipamento_id is None)
        if original in assigned or not same_target:
            pk = next_id
            next_id += 1
        else:
            pk = original
        assigned.add(pk)
        saved, _ = old.objects.using(alias).update_or_create(pk=pk, defaults=values)
        old.objects.using(alias).filter(pk=pk).update(criado_em=values['criado_em'])
        return saved

    # Recreate local rows, remapping colliding PKs from independent tables.
    for category, source in sources:
        fields = [field.attname for field in source._meta.concrete_fields]
        for row in source.objects.using(alias).all():
            values = {field: getattr(row, field) for field in fields}
            saved = restore_booking(values, category)
            typed_mapping[(category, row.pk)] = saved.pk
            if category == 'servico':
                ids = source.equipamentos.through.objects.using(alias).filter(agendaservico_id=row.pk).values_list('equipamento_id', flat=True)
                old.equipamentos.through.objects.using(alias).filter(agendamento_id=saved.pk).delete()
                old.equipamentos.through.objects.using(alias).bulk_create([
                    old.equipamentos.through(agendamento_id=saved.pk, equipamento_id=pk) for pk in ids])
            event.objects.using(alias).filter(**{'agenda_'+category+'_id': row.pk}).update(agendamento_id=saved.pk)
            receipt.objects.using(alias).filter(**{'agenda_'+category+'_id': row.pk}).update(agendamento_id=saved.pk)
    if payload is not None:
        for row in payload['bookings']:
            saved = restore_booking(dict(row))
            legacy_mapping[row['id']] = saved.pk
        for key, model in [('events', event), ('receipts', receipt), ('remote_links', apps.get_model('agenda', 'ReservaAgroHub'))]:
            occupied = set(model.objects.using(alias).values_list('pk', flat=True))
            next_related_id = max(occupied | {row['id'] for row in payload[key]}, default=0) + 1
            for row in payload[key]:
                values = dict(row)
                original = values['agendamento_id']
                category = payload.get('local_booking_categories', {}).get(str(original))
                values['agendamento_id'] = (typed_mapping[(category, original)] if category
                    else legacy_mapping.get(original, original))
                if values['id'] in occupied:
                    values['id'] = next_related_id
                    next_related_id += 1
                occupied.add(values['id'])
                saved = model.objects.using(alias).create(**values)
                timestamp = 'instante' if key == 'events' else 'criado_em' if key == 'receipts' else 'atualizado_em'
                model.objects.using(alias).filter(pk=saved.pk).update(**{timestamp: values[timestamp]})
        for values in payload.get('equipment_links', []):
            old.equipamentos.through.objects.using(alias).get_or_create(
                agendamento_id=legacy_mapping[values['agendamento_id']], equipamento_id=values['equipamento_id'])
        for values in payload.get('visit_locks', []):
            apps.get_model('agenda', 'ControleAgendaVisitas').objects.using(alias).get_or_create(**values)
    for statement in schema_editor.connection.ops.sequence_reset_sql(no_style(), [old, event, receipt, apps.get_model('agenda', 'ReservaAgroHub')]):
        schema_editor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [('agenda', '0013_agendaequipamento_agendaservico_and_more'), ('integracoes', '0002_remove_pedidointegracao_agendamento_and_more')]
    operations = [
        migrations.RunPython(copy_rows, restore_rows),
        migrations.RemoveField(model_name='eventoagendamento', name='agendamento'),
        migrations.AddConstraint(model_name='eventoagendamento', constraint=models.CheckConstraint(condition=(
            models.Q(agenda_servico__isnull=False, agenda_equipamento__isnull=True) | models.Q(agenda_servico__isnull=True, agenda_equipamento__isnull=False)), name='evento_exatamente_uma_agenda')),
    ]
