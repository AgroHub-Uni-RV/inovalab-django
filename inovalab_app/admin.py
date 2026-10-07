from django.contrib import admin
from inovalab_app.models import (AgendaEquipamento, AgendaServico, AgendaVisita, Banner,
                                Equipamento, EventoAgendamento, EventoTarefa, Material, Servico, Tarefa)

for model in (Servico, Equipamento, Material, Tarefa, EventoTarefa,
              AgendaServico, AgendaEquipamento, AgendaVisita, EventoAgendamento, Banner):
    admin.site.register(model)
