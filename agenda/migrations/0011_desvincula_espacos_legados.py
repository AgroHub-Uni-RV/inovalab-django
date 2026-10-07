from django.db import migrations, models


def preserve_spaces(apps, schema_editor):
    bookings = apps.get_model('agenda', 'Agendamento')
    spaces = apps.get_model('catalogo', 'Espaco')
    alias = schema_editor.connection.alias
    for space in spaces.objects.using(alias).all().iterator():
        bookings.objects.using(alias).filter(espaco_id=space.pk).update(
            espaco_legado_id=space.pk, espaco_legado_nome=space.nome,
        )


def restore_references(apps, schema_editor):
    # Reversão recupera somente espaços referenciados, com ID/nome e demais valores padrão.
    bookings = apps.get_model('agenda', 'Agendamento')
    spaces = apps.get_model('catalogo', 'Espaco')
    alias = schema_editor.connection.alias
    for booking in bookings.objects.using(alias).filter(espaco_legado_id__isnull=False).iterator():
        spaces.objects.using(alias).get_or_create(
            pk=booking.espaco_legado_id, defaults={'nome': booking.espaco_legado_nome},
        )
        bookings.objects.using(alias).filter(pk=booking.pk).update(espaco_id=booking.espaco_legado_id)


class Migration(migrations.Migration):
    dependencies = [
        ('agenda', '0010_quantidade_pessoas_visitas'),
        ('catalogo', '0006_fotos_iniciais_webp'),
    ]

    operations = [
        migrations.RemoveConstraint(model_name='agendamento', name='agenda_exatamente_um_alvo'),
        migrations.AddField(
            model_name='agendamento', name='espaco_legado_id',
            field=models.PositiveBigIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='agendamento', name='espaco_legado_nome',
            field=models.CharField(blank=True, default='', editable=False, max_length=150),
        ),
        migrations.RunPython(preserve_spaces, restore_references),
        migrations.RemoveField(model_name='agendamento', name='espaco'),
        migrations.AddConstraint(
            model_name='agendamento',
            constraint=models.CheckConstraint(condition=(
                models.Q(visita=False) & (
                    models.Q(servico__isnull=False, equipamento__isnull=True, espaco_legado_id__isnull=True)
                    | models.Q(servico__isnull=True, equipamento__isnull=False, espaco_legado_id__isnull=True)
                    | models.Q(servico__isnull=True, equipamento__isnull=True, espaco_legado_id__isnull=False)
                ) | models.Q(visita=True, servico__isnull=True, equipamento__isnull=True, espaco_legado_id__isnull=True)
            ), name='agenda_exatamente_um_alvo'),
        ),
    ]
