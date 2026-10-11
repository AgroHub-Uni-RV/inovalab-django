from django.db import transaction
from pathlib import Path
from inovalab_app.catalogo.equipment_photos import INITIAL_EQUIPMENT_PHOTOS


INITIAL_EQUIPMENT = (
    ('plotter-impressao', 'Plotter de impressão', 'Imprima em alta qualidade.'),
    ('impressora-3d', 'Impressora 3D', 'Modelagem e impressão com alta precisão.'),
    ('corte-laser', 'Corte a Laser', 'Cortes e gravações em diversos materiais.'),
    ('plotter-corte', 'Plotter de corte de madeira e acrílico', 'Realize cortes precisos em madeira, acrílico e outros materiais.'),
    ('realidade-virtual', 'Óculos VR',
     'Dispositivo para experiências imersivas, simulações e validação de ambientes digitais.'),
    ('scanner-3d', 'Scanner 3D',
     'Digitalização de objetos para modelagem, prototipagem e impressão 3D.'),
)


def seed_initial_resources(equipment_model, using='default', *, restore=False):
    """Carga repetível por código estável, preservando edições locais."""
    count = 0
    with transaction.atomic(using=using):
        for code, name, description in INITIAL_EQUIPMENT:
            defaults = {'nome': name, 'descricao': description, 'status': 'disponivel'}
            if any(field.name == 'foto' for field in equipment_model._meta.fields):
                defaults['foto'] = 'iniciais/' + INITIAL_EQUIPMENT_PHOTOS[code]
            if any(field.name == 'foto_webp' for field in equipment_model._meta.fields):
                image = Path(__file__).parent.parent / 'static' / 'inovalab_app' / 'catalogo' / 'equipamentos' / INITIAL_EQUIPMENT_PHOTOS[code]
                defaults['foto_webp'] = image.read_bytes()
            if restore:
                defaults['excluido_em'] = None
                _, created = equipment_model.objects.using(using).update_or_create(
                    codigo_inicial=code, defaults=defaults)
            else:
                _, created = equipment_model.objects.using(using).get_or_create(
                    codigo_inicial=code,
                    defaults=defaults,
                )
            count += created
    return count
