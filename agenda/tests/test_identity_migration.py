from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from agenda.tests.migration_helpers import PrivateArchiveMixin


class BookingIdentityMigrationTests(PrivateArchiveMixin, TransactionTestCase):
    def test_removing_requester_preserves_bookings_creators_periods_and_history(self):
        previous = [('agenda', '0005_agendamento_avaliado_em_agendamento_avaliado_por_and_more')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        current = [('agenda', '0012_identifica_reservas_recebidas_agrohub'), ('catalogo', '0007_remove_espaco'), ('integracoes', '0001_initial')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            actor = get_user_model().objects.create_user(username='criador-legado')
            service = apps.get_model('catalogo', 'Servico').objects.create(nome='Serviço legado')
            start = datetime.fromisoformat('2026-11-01T14:00:37.123456-03:00')
            end = datetime.fromisoformat('2026-11-03T15:00:41.654321-03:00')
            booking = apps.get_model('agenda', 'Agendamento').objects.create(
                servico=service, criado_por_id=actor.pk, requerente='Outra pessoa', motivo='Legado',
                inicio=start, fim=end, versao=4, situacao='pendente')
            event = apps.get_model('agenda', 'EventoAgendamento').objects.create(
                agendamento=booking, ator_id=actor.pk, ator_nome='criador-legado', acao='criar',
                alteracoes={'requerente': {'anterior': None, 'novo': 'Outra pessoa'}})
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            apps = executor.loader.project_state(current).apps
            migrated = apps.get_model('agenda', 'Agendamento').objects.get(pk=booking.pk)
            self.assertEqual(migrated.observacoes, '')
            self.assertEqual((migrated.criado_por_id, migrated.inicio, migrated.fim, migrated.versao,
                              migrated.situacao, migrated.motivo),
                             (actor.pk, start, end, 4, 'pendente', 'Legado'))
            migrated_event = apps.get_model('agenda', 'EventoAgendamento').objects.get(pk=event.pk)
            self.assertEqual(migrated_event.alteracoes, event.alteracoes)
            self.assertEqual(migrated_event.ator_id, actor.pk)
            external = apps.get_model('agenda', 'Agendamento').objects.create(
                servico_id=service.pk, motivo='Integração', inicio=start, fim=end)
            self.assertIsNone(external.criado_por_id)
        finally:
            MigrationExecutor(connection).migrate(latest)
