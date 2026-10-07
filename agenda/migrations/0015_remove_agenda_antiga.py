from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('agenda', '0014_copia_agendas_locais'), ('integracoes', '0003_finaliza_agendas_tipadas')]
    operations = [migrations.DeleteModel(name='ReservaAgroHub'), migrations.DeleteModel(name='ControleAgendaVisitas'), migrations.DeleteModel(name='Agendamento')]
