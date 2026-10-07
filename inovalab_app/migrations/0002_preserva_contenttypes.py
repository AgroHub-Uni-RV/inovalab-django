from django.db import migrations

# Frozen mapping: future domain changes must not alter this migration.
MODEL_LABELS = {
    'servico': 'catalogo', 'equipamento': 'catalogo', 'material': 'materiais',
    'tarefa': 'tarefas', 'eventotarefa': 'tarefas', 'banner': 'conteudo',
    'agendaservico': 'agenda', 'agendaequipamento': 'agenda',
    'agendavisita': 'agenda', 'eventoagendamento': 'agenda',
}


def preserve_content_types(apps, schema_editor):
    content_types = apps.get_model('contenttypes', 'ContentType').objects.using(schema_editor.connection.alias)
    for model, old_label in MODEL_LABELS.items():
        if (content_types.filter(app_label=old_label, model=model).exists()
                and content_types.filter(app_label='inovalab_app', model=model).exists()):
            raise RuntimeError(f'ContentType conflitante: {old_label}.{model}.')
    for model, old_label in MODEL_LABELS.items():
        content_types.filter(app_label=old_label, model=model).update(app_label='inovalab_app')


class Migration(migrations.Migration):
    dependencies = [('inovalab_app', '0001_initial'), ('contenttypes', '0002_remove_content_type_name')]
    operations = [migrations.RunPython(preserve_content_types)]
