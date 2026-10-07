from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from catalogo.initial_resources import seed_initial_resources
from catalogo.models import Equipamento


class Command(BaseCommand):
    help = 'Carrega máquinas iniciais, preservando cadastros já carregados e suas edições.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        equipment = seed_initial_resources(Equipamento, using=options['database'])
        self.stdout.write(self.style.SUCCESS(
            f'Carga concluída: {equipment} equipamento(s) criado(s); existentes preservados.'
        ))
