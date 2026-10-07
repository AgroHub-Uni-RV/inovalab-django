from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from inovalab_app.upgrade import UpgradeError, validate_existing_schema


class Command(BaseCommand):
    help = 'Verifica, sem alterar dados, se o banco pode ser adotado pelo app único.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')

    def handle(self, *args, **options):
        try:
            existing = validate_existing_schema(connections[options['database']])
        except UpgradeError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS('Banco existente compatível.' if existing else 'Instalação nova: nenhuma tabela de negócio existente.'))
