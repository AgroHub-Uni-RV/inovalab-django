from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

class Command(BaseCommand):
    help = 'Explica a substituição do catálogo por serviços definidos por solicitação.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        self.stdout.write('Serviços são definidos por solicitação; nenhum serviço predefinido foi carregado.')
