from django.db import migrations


PHOTOS = (
    ('plotter-impressao', 'png'), ('impressora-3d', 'png'),
    ('corte-laser', 'png'), ('plotter-corte', 'png'),
    ('realidade-virtual', 'jpg'), ('scanner-3d', 'jpg'),
)


def update_photos(apps, schema_editor, reverse=False):
    equipment = apps.get_model('catalogo', 'Equipamento')
    for name, extension in PHOTOS:
        old = f'iniciais/{name}.{extension}'
        new = f'iniciais/{name}.webp'
        if reverse:
            old, new = new, old
        equipment.objects.using(schema_editor.connection.alias).filter(foto=old).update(foto=new)


def revert_photos(apps, schema_editor):
    update_photos(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [('catalogo', '0005_equipamento_foto')]
    operations = [migrations.RunPython(update_photos, revert_photos)]
