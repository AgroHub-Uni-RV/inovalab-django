import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from agenda.legacy_archive import archive_legacy
from agenda.tests.migration_helpers import PrivateArchiveMixin

PREVIOUS = [('agenda', '0012_identifica_reservas_recebidas_agrohub'), ('integracoes', '0001_initial'), ('catalogo', '0007_remove_espaco')]


class LegacyArchiveTests(PrivateArchiveMixin, SimpleTestCase):
    def test_nonempty_retired_data_requires_private_durable_directory_outside_debug(self):
        payload = {'bookings': [{'id': 5, 'motivo': 'Privado'}], 'remote_links': []}
        with override_settings(DEBUG=False, AGENDAS_LEGACY_ARCHIVE_DIR=''), patch.dict('os.environ', {'AGENDAS_LEGACY_ARCHIVE_DIR': ''}):
            with self.assertRaisesMessage(RuntimeError, 'AGENDAS_LEGACY_ARCHIVE_DIR'):
                archive_legacy(payload, database='production')
        self.assertEqual(list(Path(self.archive_directory).iterdir()), [])


class SplitMigrationTests(PrivateArchiveMixin, TransactionTestCase):
    def test_migration_preserves_typed_data_dates_m2m_audit_receipts_and_archives_removed_rows(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(PREVIOUS)
        archive = None
        try:
            apps = executor.loader.project_state(PREVIOUS).apps
            booking_model = apps.get_model('agenda', 'Agendamento')
            service = apps.get_model('catalogo', 'Servico').objects.create(nome='Serviço histórico')
            machine = apps.get_model('catalogo', 'Equipamento').objects.create(nome='Máquina histórica')
            material = apps.get_model('materiais', 'Material').objects.create(nome='PLA legado', categoria='Filamento', quantidade=10, unidade='g', fonte='Laboratório')
            actor = get_user_model().objects.create_user(username='criador-legado-split')
            period = dict(inicio=datetime.fromisoformat('2026-11-01T17:00:37.123456+00:00'),
                          fim=datetime.fromisoformat('2026-11-03T18:00:41.654321+00:00'))
            service_booking = booking_model.objects.create(pk=70, servico=service, motivo='Protótipo', observacoes='Preservar',
                material_proprio=False, material_gasto=material, material_gasto_gramas='12.125', criado_por_id=actor.pk,
                avaliado_por_id=actor.pk, avaliado_em='2026-10-06T18:00:00Z', versao=4, situacao='confirmado', **period)
            service_booking.equipamentos.add(machine)
            booking_model.objects.create(pk=71, equipamento=machine, motivo='Uso', versao=3, cancelado_em='2026-10-07T10:00:00Z', **period)
            visit = booking_model.objects.create(pk=72, visita=True, quantidade_pessoas=5,
                inicio='2026-11-10T12:00:00Z', fim='2026-11-10T13:00:00Z')
            visit.equipamentos.add(machine)
            booking_model.objects.create(pk=73, espaco_legado_id=12, espaco_legado_nome='Sala histórica', motivo='Legado', **period)
            booking_model.objects.all().update(criado_em='2026-10-01T09:00:00Z')
            client = apps.get_model('integracoes', 'ClienteIntegracao').objects.create(nome='Cliente histórico', token_digest='secret-not-archived')
            for pk in (70, 71, 72, 73):
                event = apps.get_model('agenda', 'EventoAgendamento').objects.create(pk=pk, agendamento_id=pk, ator_id=actor.pk, ator_nome='Histórico', acao='criar', alteracoes={'motivo': {'anterior': None, 'novo': 'original'}})
                apps.get_model('agenda', 'EventoAgendamento').objects.filter(pk=pk).update(instante='2026-10-01T09:30:00Z')
                apps.get_model('integracoes', 'PedidoIntegracao').objects.create(pk=pk, agendamento_id=pk, cliente=client, id_externo=f'ext-{pk}', requerente_id='pessoa', conteudo_digest=str(pk)*32)
                apps.get_model('integracoes', 'PedidoIntegracao').objects.filter(pk=pk).update(criado_em='2026-10-01T09:45:00Z')
            apps.get_model('agenda', 'ReservaAgroHub').objects.create(agendamento=visit, origem='https://provider.example/api/v1/', reserva_id=99,
                recebida=True, payload={'titulo': 'Visita original', 'solicitante': 'Pessoa remota'}, estado='registrada')
            apps.get_model('agenda', 'ControleAgendaVisitas').objects.create(pk=2)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            saved = apps.get_model('agenda', 'AgendaServico').objects.get(pk=70)
            self.assertEqual((saved.motivo, saved.observacoes, saved.versao, saved.material_gasto_id, saved.material_gasto_gramas), ('Protótipo', 'Preservar', 4, material.pk, Decimal('12.125')))
            self.assertEqual(saved.inicio.isoformat(), '2026-11-01T17:00:37.123456+00:00')
            self.assertEqual(saved.fim.isoformat(), '2026-11-03T18:00:41.654321+00:00')
            self.assertEqual(saved.criado_em.isoformat(), '2026-10-01T09:00:00+00:00')
            self.assertEqual(list(saved.equipamentos.values_list('pk', flat=True)), [machine.pk])
            self.assertEqual(saved.avaliado_por_id, actor.pk)
            self.assertEqual(saved.avaliado_em.isoformat(), '2026-10-06T18:00:00+00:00')
            equipment = apps.get_model('agenda', 'AgendaEquipamento').objects.get(pk=71)
            self.assertEqual(equipment.cancelado_em.isoformat(), '2026-10-07T10:00:00+00:00')
            for pk, field in [(70, 'agenda_servico_id'), (71, 'agenda_equipamento_id')]:
                event = apps.get_model('agenda', 'EventoAgendamento').objects.get(pk=pk)
                receipt = apps.get_model('integracoes', 'PedidoIntegracao').objects.get(pk=pk)
                self.assertEqual(getattr(event, field), pk)
                self.assertEqual(getattr(receipt, field), pk)
                self.assertEqual(event.instante.isoformat(), '2026-10-01T09:30:00+00:00')
                self.assertEqual(receipt.criado_em.isoformat(), '2026-10-01T09:45:00+00:00')
                self.assertEqual(receipt.conteudo_digest, str(pk)*32)
                self.assertEqual(receipt.id_externo, f'ext-{pk}')
            self.assertNotIn('agenda_agendamento', connection.introspection.table_names())
            self.assertEqual(apps.get_model('agenda', 'EventoAgendamento').objects.count(), 2)
            self.assertEqual(apps.get_model('integracoes', 'PedidoIntegracao').objects.count(), 2)
            archives = list(Path(self.archive_directory).glob('*.json'))
            self.assertEqual(len(archives), 1)
            archive = archives[0]
            payload = json.loads(archive.read_text(encoding='utf-8'))
            self.assertEqual({row['id'] for row in payload['bookings']}, {72, 73})
            self.assertEqual({row['id'] for row in payload['events']}, {72, 73})
            self.assertEqual({row['id'] for row in payload['receipts']}, {72, 73})
            self.assertEqual(payload['remote_links'][0]['reserva_id'], 99)
            self.assertNotIn('secret-not-archived', archive.read_text(encoding='utf-8'))
            with override_settings(AGENDAS_LEGACY_RESTORE_FILE=str(archive)):
                executor = MigrationExecutor(connection)
                executor.migrate(PREVIOUS)
            apps = executor.loader.project_state(PREVIOUS).apps
            restored = apps.get_model('agenda', 'Agendamento')
            self.assertEqual(restored.objects.count(), 4)
            self.assertEqual(restored.objects.get(pk=72).quantidade_pessoas, 5)
            self.assertEqual(restored.objects.get(pk=73).espaco_legado_nome, 'Sala histórica')
            self.assertEqual(list(restored.objects.get(pk=72).equipamentos.values_list('pk', flat=True)), [machine.pk])
            self.assertTrue(apps.get_model('agenda', 'ControleAgendaVisitas').objects.filter(pk=2).exists())
            self.assertEqual(apps.get_model('agenda', 'ReservaAgroHub').objects.get(reserva_id=99).agendamento_id, 72)
            self.assertEqual(apps.get_model('agenda', 'EventoAgendamento').objects.get(pk=72).instante.isoformat(), '2026-10-01T09:30:00+00:00')
            self.assertEqual(apps.get_model('integracoes', 'PedidoIntegracao').objects.get(pk=73).conteudo_digest, '73'*32)
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_rollback_remaps_new_equal_ids_and_restores_remote_link_to_original_category(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(PREVIOUS)
        try:
            apps = executor.loader.project_state(PREVIOUS).apps
            service = apps.get_model('catalogo', 'Servico').objects.create(nome='Serviço rollback')
            machine = apps.get_model('catalogo', 'Equipamento').objects.create(nome='Máquina rollback')
            period = dict(inicio='2026-11-01T14:00:00Z', fim='2026-11-01T15:00:00Z')
            original = apps.get_model('agenda', 'Agendamento').objects.create(pk=40, equipamento=machine, motivo='Equipamento original', **period)
            apps.get_model('agenda', 'ReservaAgroHub').objects.create(agendamento=original, origem='https://provider.example/api/v1/', reserva_id=140, estado='registrada')
            client = apps.get_model('integracoes', 'ClienteIntegracao').objects.create(nome='Cliente rollback')
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            apps.get_model('agenda', 'AgendaServico').objects.create(pk=40, servico_id=service.pk, motivo='Serviço novo', **period)
            for category in ('servico', 'equipamento'):
                target = {'agenda_' + category + '_id': 40}
                apps.get_model('agenda', 'EventoAgendamento').objects.create(ator_nome=category, acao='criar', **target)
                apps.get_model('integracoes', 'PedidoIntegracao').objects.create(cliente_id=client.pk, id_externo=category, requerente_id='pessoa', conteudo_digest=category, **target)
            archive = next(Path(self.archive_directory).glob('*.json'))
            with override_settings(AGENDAS_LEGACY_RESTORE_FILE=str(archive)):
                MigrationExecutor(connection).migrate(PREVIOUS)
            apps = MigrationExecutor(connection).loader.project_state(PREVIOUS).apps
            old = apps.get_model('agenda', 'Agendamento')
            restored_service = old.objects.get(servico_id=service.pk)
            restored_equipment = old.objects.get(equipamento_id=machine.pk)
            self.assertNotEqual(restored_service.pk, restored_equipment.pk)
            self.assertEqual(apps.get_model('agenda', 'ReservaAgroHub').objects.get(reserva_id=140).agendamento_id, restored_equipment.pk)
            for category, target in [('servico', restored_service), ('equipamento', restored_equipment)]:
                self.assertEqual(apps.get_model('agenda', 'EventoAgendamento').objects.get(ator_nome=category).agendamento_id, target.pk)
                self.assertEqual(apps.get_model('integracoes', 'PedidoIntegracao').objects.get(id_externo=category).agendamento_id, target.pk)
            appended = old.objects.create(visita=True, quantidade_pessoas=1, **period)
            self.assertGreater(appended.pk, max(restored_service.pk, restored_equipment.pk))
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_archive_write_failure_aborts_before_removing_old_rows(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(PREVIOUS)
        try:
            apps = executor.loader.project_state(PREVIOUS).apps
            apps.get_model('agenda', 'Agendamento').objects.create(visita=True, quantidade_pessoas=2,
                inicio='2026-11-10T12:00:00Z', fim='2026-11-10T13:00:00Z')
            blocked = Path(self.archive_directory) / 'not-a-directory'
            blocked.write_text('blocked', encoding='utf-8')
            with override_settings(AGENDAS_LEGACY_ARCHIVE_DIR=str(blocked)):
                with self.assertRaises(OSError):
                    MigrationExecutor(connection).migrate(latest)
            self.assertEqual(apps.get_model('agenda', 'Agendamento').objects.count(), 1)
        finally:
            MigrationExecutor(connection).migrate(latest)
