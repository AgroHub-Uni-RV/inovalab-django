from django.db import migrations


def create_administrator_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).get_or_create(name='Administradores')


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [migrations.RunPython(create_administrator_group, migrations.RunPython.noop)]
