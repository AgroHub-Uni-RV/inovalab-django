from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from catalogo.initial_resources import seed_initial_resources
from catalogo.models import Equipamento, Espaco


class Command(BaseCommand):
    help = 'Carrega máquinas e espaços iniciais, preservando cadastros já carregados e suas edições.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        equipment, spaces = seed_initial_resources(Equipamento, Espaco, using=options['database'])
        self.stdout.write(self.style.SUCCESS(
            f'Carga concluída: {equipment} equipamento(s) e {spaces} espaço(s) criado(s); existentes preservados.'
        ))
