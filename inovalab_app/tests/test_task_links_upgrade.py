from datetime import datetime, timezone
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TaskLinksUpgradeTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('inovalab_app', '0005_tarefa_prazo_do_servico')])
        self.old = executor.loader.project_state([('inovalab_app', '0005_tarefa_prazo_do_servico')]).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate([('inovalab_app', '0006_tarefas_multiplos_vinculos')])
        super().tearDown()

    def test_migration_copies_all_links_including_deleted_tasks_without_changing_old_rows(self):
        actor = get_user_model().objects.create_user('responsavel-antigo', is_active=False)
        deadline = datetime(2099, 12, 1, 18, 22, 37, 123456, tzinfo=timezone.utc)
        service = self.old.get_model('inovalab_app', 'Servico').objects.create(titulo='Preservar', descricao='Legado', prazo=deadline)
        booking = self.old.get_model('inovalab_app', 'AgendaServico').objects.create(servico=service, criado_por_id=actor.pk)
        equipment = self.old.get_model('inovalab_app', 'Equipamento').objects.create(nome='Antigo', descricao='Preservar', excluido_em=deadline)
        material = self.old.get_model('inovalab_app', 'Material').objects.create(nome='Antigo', categoria='Outro', quantidade=100, unidade='g', fonte='Lab', status='indisponivel')
        Task = self.old.get_model('inovalab_app', 'Tarefa')
        tasks = [Task.objects.create(agendamento_servico=booking, descricao='Preservar', responsavel_id=actor.pk,
                                     equipamento=equipment, material_gasto=material, quantidade_material_gasto='meia bobina',
                                     prazo_legado=deadline, versao=8, excluida_em=deleted)
                 for deleted in (None, deadline)]
        events = self.old.get_model('inovalab_app', 'EventoTarefa')
        for task in tasks:
            events.objects.create(tarefa=task, ator_id=actor.pk, ator_nome='Histórico preservado', acao='criar',
                                  status_novo='demanda', alteracoes={'anterior': True})
        before = list(Task.objects.order_by('pk').values())
        before_events = list(events.objects.order_by('pk').values())
        MigrationExecutor(connection).migrate([('inovalab_app', '0006_tarefas_multiplos_vinculos')])
        from inovalab_app.tarefas.models import EventoTarefa, Tarefa
        self.assertEqual(list(Tarefa.objects.order_by('pk').values()), before)
        self.assertEqual(list(EventoTarefa.objects.order_by('pk').values()), before_events)
        for task in Tarefa.objects.all():
            self.assertEqual(list(task.responsaveis.values_list('pk', flat=True)), [actor.pk])
            self.assertEqual(list(task.equipamentos.values_list('pk', flat=True)), [equipment.pk])
            self.assertEqual((task.materiais_gastos.get().material_id, task.materiais_gastos.get().quantidade),
                             (material.pk, 'meia bobina'))
            self.assertEqual(task.prazo, deadline)
