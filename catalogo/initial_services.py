from django.db import transaction


# Values transcribed from the PDF. Existing entries are never overwritten.
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


def seed_initial_services(service_model, using='default') -> int:
    created_count = 0
    with transaction.atomic(using=using):
        for code, name, description in INITIAL_SERVICES:
            _, created = service_model.objects.using(using).get_or_create(
                codigo_inicial=code,
                defaults={'nome': name, 'descricao': description, 'status': 'disponivel'},
            )
            created_count += created
    return created_count
