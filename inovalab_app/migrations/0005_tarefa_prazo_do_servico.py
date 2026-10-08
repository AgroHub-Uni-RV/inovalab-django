from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('inovalab_app', '0004_exige_agendamento_servico')]

    operations = [
        # Keep the physical column and all previous values intact. The operational
        # deadline is now derived from AgendaServico.servico.prazo, without a copy.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(model_name='tarefa', old_name='prazo', new_name='prazo_legado'),
                migrations.AlterField(model_name='tarefa', name='prazo_legado',
                    field=models.DateTimeField('prazo anterior', db_column='prazo', null=True, blank=True, editable=False)),
            ],
        ),
    ]
