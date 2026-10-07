from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('agenda', '0014_copia_agendas_locais'), ('integracoes', '0002_remove_pedidointegracao_agendamento_and_more')]
    operations = [migrations.RemoveField(model_name='pedidointegracao', name='agendamento'), migrations.AddConstraint(
            model_name='pedidointegracao',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('agenda_equipamento__isnull', True), ('agenda_servico__isnull', False)), models.Q(('agenda_equipamento__isnull', False), ('agenda_servico__isnull', True)), _connector='OR'), name='pedido_exatamente_uma_agenda'),
        )]
