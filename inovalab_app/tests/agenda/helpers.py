from datetime import datetime, timezone
from inovalab_app.agenda.models import AgendaServico
from inovalab_app.catalogo.models import Servico


def make_service(*, titulo='Projeto de teste', descricao='Descrição do pedido', prazo=None):
    return Servico.objects.create(titulo=titulo, descricao=descricao,
        prazo=prazo or datetime(2099, 11, 1, 18, tzinfo=timezone.utc))


def make_booking(*, actor=None, service=None, prazo=None, titulo='Projeto de teste', descricao='Descrição do pedido', **control):
    service = service or make_service(prazo=prazo, titulo=titulo, descricao=descricao)
    return AgendaServico.objects.create(servico=service, criado_por=actor, **control)


def service_data(**overrides):
    return {'categoria': 'servico', 'titulo': 'Projeto de teste', 'descricao': 'Descrição do pedido',
            'prazo': datetime(2099, 11, 1, 18, tzinfo=timezone.utc), **overrides}


def service_web_data(**overrides):
    return {'categoria': 'servico', 'titulo': 'Projeto de teste', 'descricao': 'Descrição do pedido',
            'prazo_data': '2099-11-01', 'prazo_hora': '15:00', **overrides}
