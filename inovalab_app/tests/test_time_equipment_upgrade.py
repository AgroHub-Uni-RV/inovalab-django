from datetime import timedelta
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class TimeEquipmentUpgradeTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('inovalab_app', '0007_realizacao_visitas')])
        self.old = executor.loader.project_state([('inovalab_app', '0007_realizacao_visitas')]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_upgrade_recovers_time_and_loads_missing_defaults_without_overwriting_customizations(self):
        actor = get_user_model().objects.create_user('migracao-relogio')
        now = timezone.now()
        Service = self.old.get_model('inovalab_app', 'Servico')
        Booking = self.old.get_model('inovalab_app', 'AgendaServico')
        Task = self.old.get_model('inovalab_app', 'Tarefa')
        Event = self.old.get_model('inovalab_app', 'EventoTarefa')
        Equipment = self.old.get_model('inovalab_app', 'Equipamento')
        Equipment.objects.all().delete()
        edited = Equipment.objects.create(codigo_inicial='impressora-3d', nome='Nome local',
            descricao='Descrição local', foto='', excluido_em=now, status='indisponivel')
        custom = Equipment.objects.create(nome='Personalizado')
        service = Service.objects.create(titulo='Migrar', descricao='Preservar', prazo=now + timedelta(days=1))
        booking = Booking.objects.create(servico=service)
        task = Task.objects.create(agendamento_servico=booking, responsavel_id=actor.pk,
            descricao='Preservar', inicio=now - timedelta(hours=1), status='criacao', versao=8)
        for seconds, before, after in [(0, 'demanda', 'criacao'), (30, 'criacao', 'avaliacao'), (120, 'avaliacao', 'criacao')]:
            event = Event.objects.create(tarefa=task, ator_nome='Legado', acao='alterar_status',
                status_anterior=before, status_novo=after, alteracoes={'preservado': True})
            Event.objects.filter(pk=event.pk).update(instante=now - timedelta(seconds=180-seconds))
        events = list(Event.objects.values())
        # No historical evidence: start at upgrade time, do not count evaluation.
        unknown = Task.objects.create(agendamento_servico=booking, responsavel_id=actor.pk,
            descricao='Sem eventos', inicio=now - timedelta(days=10), status='criacao')
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        from inovalab_app.catalogo.models import Equipamento
        from inovalab_app.tarefas.models import Tarefa, EventoTarefa
        upgraded = Tarefa.objects.get(pk=task.pk)
        self.assertEqual(upgraded.tempo_criacao, timedelta(seconds=30))
        self.assertEqual(upgraded.criacao_desde, now - timedelta(seconds=60))
        self.assertEqual(upgraded.versao, 8)
        self.assertEqual(list(EventoTarefa.objects.values()), events)
        self.assertGreaterEqual(Tarefa.objects.get(pk=unknown.pk).criacao_desde, now)
        edited = Equipamento.objects.get(pk=edited.pk)
        self.assertEqual((edited.nome, edited.descricao, edited.foto.name, edited.status),
                         ('Nome local', 'Descrição local', '', 'indisponivel'))
        self.assertIsNotNone(edited.excluido_em)
        self.assertEqual(Equipamento.objects.get(pk=custom.pk).nome, 'Personalizado')
        self.assertEqual(Equipamento.objects.filter(codigo_inicial__isnull=False).count(), 6)
        for equipment in Equipamento.objects.exclude(foto=''):
            with Image.open(BytesIO(bytes(equipment.foto_webp))) as image:
                self.assertEqual(image.format, 'WEBP')
