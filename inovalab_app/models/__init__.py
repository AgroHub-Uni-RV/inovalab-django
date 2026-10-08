from inovalab_app.catalogo.models import Equipamento, Servico, ServicoLegado
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.models import EventoTarefa, Tarefa, TarefaEquipamento, TarefaMaterial, TarefaResponsavel
from inovalab_app.agenda.models import AgendaEquipamento, AgendaServico, AgendaVisita, EventoAgendamento
from inovalab_app.conteudo.models import Banner

__all__ = ['Servico', 'ServicoLegado', 'Equipamento', 'Material', 'Tarefa', 'EventoTarefa',
           'TarefaEquipamento', 'TarefaMaterial', 'TarefaResponsavel',
           'AgendaServico', 'AgendaEquipamento', 'AgendaVisita', 'EventoAgendamento', 'Banner']
