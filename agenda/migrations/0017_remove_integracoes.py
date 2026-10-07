from django.db import migrations
from django.db.migrations.recorder import MigrationRecorder

from agenda.migrations._retired_integrations import remove_retired_tables


def remove_integrations(apps, schema_editor):
    remove_retired_tables(schema_editor)
    alias = schema_editor.connection.alias
    # Inclui permissões e suas associações; preserva contas e grupos.
    apps.get_model('contenttypes', 'ContentType').objects.using(alias).filter(
        app_label='integracoes',
    ).delete()
    MigrationRecorder(schema_editor.connection).migration_qs.filter(app='integracoes').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('agenda', '0016_agenda_visita_local'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]
    # Voltar a agenda não reinstala o módulo nem recupera suas credenciais/pedidos.
    operations = [migrations.RunPython(remove_integrations, migrations.RunPython.noop)]
