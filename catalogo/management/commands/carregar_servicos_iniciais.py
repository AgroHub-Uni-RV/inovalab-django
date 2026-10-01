from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from catalogo.initial_services import seed_initial_services
from catalogo.models import Servico


class Command(BaseCommand):
    help = 'Carrega os serviços iniciais sem duplicar ou sobrescrever edições.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        created = seed_initial_services(Servico, using=options['database'])
        self.stdout.write(self.style.SUCCESS(f'Carga concluída: {created} serviço(s) criado(s); existentes preservados.'))
