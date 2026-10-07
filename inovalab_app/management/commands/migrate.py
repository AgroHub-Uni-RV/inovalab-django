from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as DjangoMigrateCommand
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from inovalab_app.upgrade import UpgradeError, validate_existing_schema


class Command(DjangoMigrateCommand):
    """Guard adoption even when --fake-initial is called directly or by a build."""
    def handle(self, *args, **options):
        connection = connections[options.get('database', 'default')]
        applied = set(MigrationRecorder(connection).applied_migrations())
        if not options.get('plan') and ('inovalab_app', '0002_preserva_contenttypes') not in applied:
            try:
                existing = validate_existing_schema(connection)
            except UpgradeError as error:
                raise CommandError(str(error)) from error
            if existing and ('inovalab_app', '0001_initial') not in applied and not options.get('fake_initial'):
                raise CommandError('Após backup e pausa de escrita, use migrate --fake-initial para adotar as tabelas existentes.')
            if options.get('fake'):
                raise CommandError('Não use --fake na consolidação; use --fake-initial após a verificação.')
        return super().handle(*args, **options)
