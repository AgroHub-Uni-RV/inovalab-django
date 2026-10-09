from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class VisitExecutionUpgradeTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('inovalab_app', '0006_tarefas_multiplos_vinculos')])
        self.old = executor.loader.project_state([('inovalab_app', '0006_tarefas_multiplos_vinculos')]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_upgrade_preserves_facts_and_does_not_assume_realization(self):
        Visit = self.old.get_model('inovalab_app', 'AgendaVisita')
        Event = self.old.get_model('inovalab_app', 'EventoAgendamento')
        visit = Visit.objects.create(quantidade_pessoas=3, data=date(2020, 1, 2),
            hora_inicio=time(9), hora_termino=time(10), observacoes='Histórico', versao=7)
        Event.objects.create(agenda_visita=visit, ator_nome='Autor preservado', acao='criar', alteracoes={'legado': True})
        before, before_events = list(Visit.objects.values()), list(Event.objects.values())
        MigrationExecutor(connection).migrate([('inovalab_app', '0007_realizacao_visitas')])
        from inovalab_app.agenda.models import AgendaVisita, EventoAgendamento, AgendaServico
        upgraded = AgendaVisita.objects.get(pk=visit.pk)
        self.assertIsNone(upgraded.realizada_em)
        self.assertIsNone(upgraded.realizada_por_id)
        self.assertEqual(upgraded.estado_execucao, 'aguardando_encerramento')
        self.assertEqual(list(AgendaVisita.objects.values(*before[0].keys())), before)
        self.assertEqual(list(EventoAgendamento.objects.values()), before_events)
        self.assertNotIn('realizada_em', {field.name for field in AgendaServico._meta.fields})
