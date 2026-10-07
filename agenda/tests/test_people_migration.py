from datetime import datetime

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class VisitPeopleMigrationTests(TransactionTestCase):
    def test_existing_visits_get_one_person_without_changing_pending_payload(self):
        previous = [('agenda', '0009_reserva_agrohub')]
        current = [('agenda', '0010_quantidade_pessoas_visitas')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            Booking = apps.get_model('agenda', 'Agendamento')
            times = {'inicio': datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                     'fim': datetime.fromisoformat('2026-11-01T15:00:00-03:00')}
            visit = Booking.objects.create(visita=True, **times)
            equipment = apps.get_model('catalogo', 'Equipamento').objects.create(nome='Equipamento legado')
            resource = Booking.objects.create(equipamento=equipment, motivo='Uso', **times)
            payload = {'observacoes': 'inovalab-visita:referencia-anterior', 'quantidade_pessoas': 1}
            sync = apps.get_model('agenda', 'ReservaAgroHub').objects.create(agendamento=visit,
                origem='https://example.test/api/v1/', estado='incerta', payload=payload)
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            apps = executor.loader.project_state(current).apps
            self.assertEqual(apps.get_model('agenda', 'Agendamento').objects.get(pk=visit.pk).quantidade_pessoas, 1)
            self.assertIsNone(apps.get_model('agenda', 'Agendamento').objects.get(pk=resource.pk).quantidade_pessoas)
            saved = apps.get_model('agenda', 'ReservaAgroHub').objects.get(pk=sync.pk)
            self.assertEqual((saved.referencia, saved.estado, saved.payload), (sync.referencia, 'incerta', payload))
        finally:
            MigrationExecutor(connection).migrate(latest)
