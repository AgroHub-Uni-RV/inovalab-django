from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('agenda', '0014_copia_agendas_locais')]
    operations = [migrations.DeleteModel(name='ReservaAgroHub'), migrations.DeleteModel(name='ControleAgendaVisitas'), migrations.DeleteModel(name='Agendamento')]
