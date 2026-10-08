import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inovalab_app.agenda.models import AgendaServico
from inovalab_app.tarefas.models import Tarefa


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Tarefa repetida no mapa: {key}.')
        result[key] = value
    return result


class Command(BaseCommand):
    help = 'Vincula tarefas antigas a agendamentos de serviço a partir de um mapa JSON explícito.'

    def add_arguments(self, parser):
        parser.add_argument('--mapa', required=True)
        parser.add_argument('--database', default='default')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            mapping = json.loads(Path(options['mapa']).read_text(encoding='utf-8-sig'), object_pairs_hook=unique_object)
        except (OSError, ValueError) as error:
            raise CommandError(f'Mapa inválido: {error}') from error
        if not isinstance(mapping, dict) or any(
            not key.isascii() or not key.isdecimal() or int(key) < 1 or str(int(key)) != key
            or type(value) is not int or value < 1 for key, value in mapping.items()
        ):
            raise CommandError('Informe um objeto JSON com IDs de tarefas como chaves e IDs inteiros positivos de agendamentos.')
        alias = options['database']
        with transaction.atomic(using=alias):
            validated = []
            for key, booking_id in mapping.items():
                task = Tarefa.objects.using(alias).select_for_update().filter(pk=int(key)).first()
                booking = AgendaServico.objects.using(alias).select_for_update().filter(pk=booking_id).first()
                if task is None or booking is None:
                    raise CommandError(f'Tarefa {key} ou agendamento {booking_id} inexistente.')
                if task.agendamento_servico_id not in (None, booking_id):
                    raise CommandError(f'Tarefa {key} já possui outro agendamento.')
                if task.servico_legado_id and task.servico_legado_id != booking.servico_legado_id:
                    raise CommandError(f'Tarefa {key} e agendamento {booking_id} possuem serviços antigos diferentes.')
                validated.append((task.pk, booking_id))
            if not options['dry_run']:
                for task_id, booking_id in validated:
                    Tarefa.objects.using(alias).filter(pk=task_id, agendamento_servico__isnull=True).update(agendamento_servico_id=booking_id)
        self.stdout.write(self.style.SUCCESS(f'{len(validated)} vínculo(s) ' + ('validados; nenhuma alteração.' if options['dry_run'] else 'aplicados.')))
