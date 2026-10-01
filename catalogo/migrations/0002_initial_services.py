from django.db import migrations, transaction


# Frozen data: do not import current models or mutable application seed values.
INITIAL_SERVICES = (
    ('identidade-visual', 'Identidade Visual', ''),
    ('impressao-sublimatica', 'Impressão Sublimática', ''),
    ('criacao-banners', 'Criação de Banners', ''),
    ('impressao-3d', 'Impressão 3D', 'Modelagem e Impressão 3D.'),
    ('corte-laser', 'Corte a laser', 'Cortes e gravações em diversos materiais.'),
    ('plotter-recorte', 'Plotter de recorte', 'Recorte de vinil adesivo e outros materiais.'),
    ('realidade-virtual', 'Óculos de realidade virtual', 'Dispositivos para experiências imersivas.'),
    ('scanner-3d', 'Scanner 3D manual', 'Digitalização de objetos para 3D.'),
    ('plotter-impressao', 'Plotter de Impressão', 'Imprima em alta qualidade.'),
    ('consultoria-tecnica', 'Consultoria técnica', 'Suporte e orientação para o desenvolvimento do projeto.'),
    ('uso-espaco', 'Uso do espaço', 'Uso do espaço para aula, demonstração e outros.'),
)


def load_services(apps, schema_editor):
    service = apps.get_model('catalogo', 'Servico')
    alias = schema_editor.connection.alias
    with transaction.atomic(using=alias):
        for code, name, description in INITIAL_SERVICES:
            service.objects.using(alias).get_or_create(
                codigo_inicial=code,
                defaults={'nome': name, 'descricao': description, 'status': 'disponivel'},
            )


class Migration(migrations.Migration):
    dependencies = [('catalogo', '0001_initial')]
    operations = [migrations.RunPython(load_services, migrations.RunPython.noop)]
