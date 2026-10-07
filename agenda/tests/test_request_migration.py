from datetime import datetime

from django.db import connection
from django.contrib.auth import get_user_model
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from agenda.tests.migration_helpers import PrivateArchiveMixin


class BookingRequestMigrationTests(PrivateArchiveMixin, TransactionTestCase):
    def test_existing_booking_is_confirmed_and_keeps_owner_version_and_cancellation(self):
        previous = [('agenda', '0004_agendamento_material_gasto_and_more')]
        current = [('agenda', '0005_agendamento_avaliado_em_agendamento_avaliado_por_and_more')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            actor = get_user_model().objects.create_user(username='legado')
            service = apps.get_model('catalogo', 'Servico').objects.create(nome='Serviço legado')
            start = datetime.fromisoformat('2026-11-01T14:00:00-03:00')
            end = datetime.fromisoformat('2026-11-01T15:00:00-03:00')
            old = apps.get_model('agenda', 'Agendamento').objects.create(servico=service, criado_por_id=actor.pk,
                requerente='Requerente legado', motivo='Motivo legado', inicio=start, fim=end,
                versao=3, cancelado_em=end)
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            model = executor.loader.project_state(current).apps.get_model('agenda', 'Agendamento')
            migrated = model.objects.get(pk=old.pk)
            self.assertEqual((migrated.situacao, migrated.criado_por_id, migrated.versao, migrated.cancelado_em),
                             ('confirmado', actor.pk, 3, end))
            self.assertEqual((migrated.inicio, migrated.fim, migrated.requerente, migrated.motivo),
                             (start, end, 'Requerente legado', 'Motivo legado'))
            self.assertIsNone(migrated.avaliado_por_id)
            self.assertIsNone(migrated.avaliado_em)
        finally:
            MigrationExecutor(connection).migrate(latest)
