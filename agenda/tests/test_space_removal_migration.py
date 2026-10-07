from datetime import datetime

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from agenda.tests.migration_helpers import PrivateArchiveMixin


class SpaceRemovalMigrationTests(PrivateArchiveMixin, TransactionTestCase):
    def test_removal_preserves_active_and_canceled_bookings_audit_and_receipts(self):
        previous = [('agenda', '0010_quantidade_pessoas_visitas'), ('catalogo', '0006_fotos_iniciais_webp'),
                    ('integracoes', '0001_initial')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        current = [('agenda', '0012_identifica_reservas_recebidas_agrohub'), ('catalogo', '0007_remove_espaco'), ('integracoes', '0001_initial')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            space = apps.get_model('catalogo', 'Espaco').objects.create(nome='Sala histórica', status='ocupado')
            booking_model = apps.get_model('agenda', 'Agendamento')
            start = datetime.fromisoformat('2026-11-01T14:00:00-03:00')
            end = datetime.fromisoformat('2026-11-01T15:00:00-03:00')
            bookings = [booking_model.objects.create(
                espaco=space, motivo='Reserva antiga', observacoes='Notas', inicio=start, fim=end,
                versao=3, situacao='pendente', cancelado_em=canceled,
            ) for canceled in (None, end)]
            visit = booking_model.objects.create(visita=True, quantidade_pessoas=5, inicio=start, fim=end)
            changes = {'categoria': {'anterior': None, 'novo': 'espaco'}, 'objeto': {'anterior': None, 'novo': space.pk}}
            event = apps.get_model('agenda', 'EventoAgendamento').objects.create(
                agendamento=bookings[0], ator_nome='Conta antiga', acao='criar', alteracoes=changes,
            )
            client = apps.get_model('integracoes', 'ClienteIntegracao').objects.create(nome='Legado')
            receipt = apps.get_model('integracoes', 'PedidoIntegracao').objects.create(
                cliente=client, agendamento=bookings[0], id_externo='antigo', requerente_id='1', conteudo_digest='a' * 64,
            )
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            apps = executor.loader.project_state(current).apps
            with self.assertRaises(LookupError):
                apps.get_model('catalogo', 'Espaco')
            self.assertNotIn('catalogo_espaco', connection.introspection.table_names())
            for original in bookings:
                saved = apps.get_model('agenda', 'Agendamento').objects.get(pk=original.pk)
                self.assertEqual((saved.espaco_legado_id, saved.espaco_legado_nome, saved.visita),
                                 (space.pk, 'Sala histórica', False))
                for field in ('motivo', 'observacoes', 'inicio', 'fim', 'versao', 'situacao', 'cancelado_em', 'criado_em'):
                    self.assertEqual(getattr(saved, field), getattr(original, field))
            self.assertEqual(apps.get_model('agenda', 'Agendamento').objects.get(pk=visit.pk).quantidade_pessoas, 5)
            saved_event = apps.get_model('agenda', 'EventoAgendamento').objects.get(pk=event.pk)
            self.assertEqual((saved_event.agendamento_id, saved_event.alteracoes), (bookings[0].pk, changes))
            saved_receipt = apps.get_model('integracoes', 'PedidoIntegracao').objects.get(pk=receipt.pk)
            self.assertEqual((saved_receipt.agendamento_id, saved_receipt.conteudo_digest), (bookings[0].pk, 'a' * 64))
            executor = MigrationExecutor(connection)
            executor.migrate(previous)
            apps = executor.loader.project_state(previous).apps
            self.assertEqual(apps.get_model('catalogo', 'Espaco').objects.get(pk=space.pk).nome, 'Sala histórica')
            self.assertEqual(apps.get_model('agenda', 'Agendamento').objects.get(pk=bookings[0].pk).espaco_id, space.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)
