from datetime import datetime

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class VisitMigrationTests(TransactionTestCase):
    def test_existing_space_and_audit_survive_visit_migration(self):
        previous = [('agenda', '0007_agendamento_observacoes')]
        current = [('agenda', '0008_visitas_e_espacos_legados')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            space = apps.get_model('catalogo', 'Espaco').objects.create(nome='Sala legada')
            booking = apps.get_model('agenda', 'Agendamento').objects.create(
                espaco=space, motivo='Reserva anterior', observacoes='Notas anteriores',
                inicio=datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                fim=datetime.fromisoformat('2026-11-01T15:00:00-03:00'), versao=3,
            )
            changes = {'motivo': {'anterior': '', 'novo': 'Reserva anterior'}}
            event = apps.get_model('agenda', 'EventoAgendamento').objects.create(
                agendamento=booking, ator_nome='Conta anterior', acao='criar', alteracoes=changes,
            )
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            apps = executor.loader.project_state(current).apps
            saved = apps.get_model('agenda', 'Agendamento').objects.get(pk=booking.pk)
            self.assertEqual((saved.espaco_id, saved.visita, saved.motivo, saved.observacoes, saved.versao),
                             (space.pk, False, 'Reserva anterior', 'Notas anteriores', 3))
            self.assertEqual((saved.inicio, saved.fim), (booking.inicio, booking.fim))
            saved_event = apps.get_model('agenda', 'EventoAgendamento').objects.get(pk=event.pk)
            self.assertEqual((saved_event.agendamento_id, saved_event.ator_nome, saved_event.alteracoes),
                             (booking.pk, 'Conta anterior', changes))
            self.assertTrue(apps.get_model('agenda', 'ControleAgendaVisitas').objects.filter(pk=1).exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
