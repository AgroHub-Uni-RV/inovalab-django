from django.db import migrations


# Dados congelados das imagens fornecidas em 06/10/2026.
INITIAL_EQUIPMENT = (
    ('plotter-impressao', 'Plotter de impressão', 'Imprima em alta qualidade.'),
    ('impressora-3d', 'Impressora 3D', 'Modelagem e impressão com alta precisão.'),
    ('corte-laser', 'Corte a laser', 'Cortes e gravações em diversos materiais.'),
    ('plotter-corte', 'Plotter de corte', 'Realize cortes precisos em diversos materiais.'),
    ('realidade-virtual', 'Óculos de realidade virtual',
     'Dispositivo para experiências imersivas, simulações e validação de ambientes digitais.'),
    ('scanner-3d', 'Scanner 3D manual',
     'Digitalização de objetos para modelagem, prototipagem e impressão 3D.'),
)

INITIAL_SPACES = (
    ('secretaria', 'Secretaria', None, True),
    ('sala-01', 'Sala 01', 4, False),
    ('sala-02', 'Sala 02', 4, False),
    ('area-convivencia', 'Área de convivência', 24, False),
    ('sala-03', 'Sala 03', 4, False),
    ('sala-04', 'Sala 04', 4, False),
    ('coworking', 'Espaço de coworking', 40, False),
    ('laboratorio-maker', 'Laboratório maker', None, True),
    ('laboratorio-robotica', 'Laboratório de robótica', None, True),
)


def load_resources(apps, schema_editor):
    equipment = apps.get_model('catalogo', 'Equipamento')
    space = apps.get_model('catalogo', 'Espaco')
    alias = schema_editor.connection.alias
    for code, name, description in INITIAL_EQUIPMENT:
        equipment.objects.using(alias).get_or_create(
            codigo_inicial=code,
            defaults={'nome': name, 'descricao': description, 'status': 'disponivel'},
        )
    for code, name, capacity, restricted in INITIAL_SPACES:
        space.objects.using(alias).get_or_create(
            codigo_inicial=code,
            defaults={'nome': name, 'capacidade_maxima_de_pessoas': capacity,
                      'somente_administradores': restricted, 'status': 'disponivel'},
        )


class Migration(migrations.Migration):
    dependencies = [('catalogo', '0003_recursos_iniciais')]
    operations = [migrations.RunPython(load_resources, migrations.RunPython.noop)]
