from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('agenda', '0011_desvincula_espacos_legados'),
        ('catalogo', '0006_fotos_iniciais_webp'),
    ]
    operations = [migrations.DeleteModel(name='Espaco')]
