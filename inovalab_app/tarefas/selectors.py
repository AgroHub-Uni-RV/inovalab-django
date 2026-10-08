from inovalab_app.adapters.host import is_business_admin
from inovalab_app.tarefas.models import Tarefa


def visible_tasks(actor):
    queryset = Tarefa.objects.filter(excluida_em__isnull=True).select_related('agendamento_servico__servico', 'responsavel', 'equipamento', 'material_gasto')
    if not actor.is_authenticated or not actor.is_active:
        return queryset.none()
    return queryset if is_business_admin(actor) else queryset.filter(responsavel=actor)
