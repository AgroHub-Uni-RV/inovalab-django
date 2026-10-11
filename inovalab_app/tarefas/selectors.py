from inovalab_app.adapters.host import is_business_admin
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.catalogo.models import Equipamento
from django.db.models import Prefetch


def visible_tasks(actor):
    queryset = Tarefa.objects.filter(excluida_em__isnull=True).select_related(
        'agendamento_servico__servico', 'responsavel', 'equipamento', 'material_gasto').defer(
        'equipamento__foto_webp').prefetch_related(
        'responsaveis', Prefetch('equipamentos', queryset=Equipamento.objects.defer('foto_webp')), 'materiais_gastos__material')
    if not actor.is_authenticated or not actor.is_active:
        return queryset.none()
    return queryset if is_business_admin(actor) else queryset.filter(responsaveis=actor).distinct()
