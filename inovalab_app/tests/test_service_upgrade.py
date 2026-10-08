from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ServiceUpgradeTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('inovalab_app', '0002_preserva_contenttypes')])
        self.old = executor.loader.project_state([('inovalab_app', '0002_preserva_contenttypes')]).apps
        self.actor = get_user_model().objects.create_user('autor-migracao')
        self.legacy = self.old.get_model('inovalab_app', 'Servico').objects.create(nome='Protótipo', descricao='Catálogo')
        start = datetime(2026, 10, 10, 9, 0, 37, 123456, tzinfo=timezone.utc)
        Booking = self.old.get_model('inovalab_app', 'AgendaServico')
        self.bookings = [Booking.objects.create(servico_id=self.legacy.pk, motivo='Pedido antigo',
            inicio=start, fim=start + timedelta(hours=1), criado_por_id=self.actor.pk) for _ in range(2)]
        self.task = self.old.get_model('inovalab_app', 'Tarefa').objects.create(
            servico_id=self.legacy.pk, responsavel_id=self.actor.pk, descricao='Tarefa preservada', versao=8)
        self.old.get_model('inovalab_app', 'EventoTarefa').objects.create(tarefa_id=self.task.pk,
            ator_id=self.actor.pk, ator_nome='Autor antigo', acao='criar', status_novo='demanda', alteracoes={'legado': True})
        MigrationExecutor(connection).migrate([('inovalab_app', '0003_prepara_servicos_solicitados')])

    def tearDown(self):
        from inovalab_app.tarefas.models import Tarefa
        Tarefa.objects.all().delete()
        MigrationExecutor(connection).migrate([('inovalab_app', '0004_exige_agendamento_servico')])
        super().tearDown()

    def apply_map(self, value, **kwargs):
        with TemporaryDirectory() as directory:
            file = Path(directory) / 'mapa.json'
            file.write_text(json.dumps(value), encoding='utf-8')
            call_command('vincular_tarefas_servicos', mapa=str(file), stdout=StringIO(), **kwargs)

    def test_services_are_individualized_without_changing_booking_task_or_history_ids(self):
        from inovalab_app.agenda.models import AgendaServico
        from inovalab_app.tarefas.models import Tarefa
        rows = list(AgendaServico.objects.filter(pk__in=[row.pk for row in self.bookings]))
        self.assertEqual(len({row.servico_id for row in rows}), 2)
        self.assertEqual(rows[0].servico.descricao, 'Pedido antigo')
        self.assertEqual(rows[0].servico.prazo, self.bookings[0].fim)
        self.assertEqual(rows[0].inicio_legado, self.bookings[0].inicio)
        self.apply_map({str(self.task.pk): rows[0].pk})
        MigrationExecutor(connection).migrate([('inovalab_app', '0004_exige_agendamento_servico')])
        task = Tarefa.objects.get(pk=self.task.pk)
        self.assertEqual((task.agendamento_servico_id, task.versao), (rows[0].pk, 8))
        self.assertEqual(task.eventos.get().alteracoes, {'legado': True})

    def test_migration_blocks_even_when_only_one_candidate_exists(self):
        with self.assertRaisesMessage(RuntimeError, str(self.task.pk)):
            MigrationExecutor(connection).migrate([('inovalab_app', '0004_exige_agendamento_servico')])

    def test_dry_run_and_invalid_map_do_not_partially_assign_tasks(self):
        from inovalab_app.tarefas.models import Tarefa
        self.apply_map({str(self.task.pk): self.bookings[0].pk}, dry_run=True)
        self.assertIsNone(Tarefa.objects.get(pk=self.task.pk).agendamento_servico_id)
        with self.assertRaises(CommandError):
            self.apply_map({str(self.task.pk): self.bookings[0].pk, '999999': self.bookings[1].pk})
        self.assertIsNone(Tarefa.objects.get(pk=self.task.pk).agendamento_servico_id)

    def test_map_rejects_other_legacy_service_and_reassignment(self):
        from inovalab_app.catalogo.models import ServicoLegado
        from inovalab_app.agenda.models import AgendaServico
        other = ServicoLegado.objects.create(nome='Outro serviço')
        AgendaServico.objects.filter(pk=self.bookings[1].pk).update(servico_legado=other)
        with self.assertRaises(CommandError):
            self.apply_map({str(self.task.pk): self.bookings[1].pk})
        self.apply_map({str(self.task.pk): self.bookings[0].pk})
        self.apply_map({str(self.task.pk): self.bookings[0].pk})
        with self.assertRaises(CommandError):
            self.apply_map({str(self.task.pk): self.bookings[1].pk})
