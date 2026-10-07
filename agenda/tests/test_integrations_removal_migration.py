from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

from agenda.models import AgendaServico, AgendaEquipamento, AgendaVisita, EventoAgendamento
from agenda.tests.migration_helpers import PrivateArchiveMixin
from catalogo.models import Servico, Equipamento


class IntegrationsRemovalMigrationTests(PrivateArchiveMixin, TransactionTestCase):
    def create_retired_tables(self, target_table):
        quote = connection.ops.quote_name
        with connection.schema_editor() as editor:
            editor.execute('CREATE TABLE integracoes_clienteintegracao (id integer PRIMARY KEY)')
            editor.execute(
                'CREATE TABLE integracoes_pedidointegracao ('
                'id integer PRIMARY KEY, cliente_id integer REFERENCES integracoes_clienteintegracao(id), '
                f'agendamento_id bigint REFERENCES {quote(target_table)}(id))'
            )
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO integracoes_clienteintegracao (id) VALUES (1)')

    def test_new_database_does_not_create_retired_tables_or_permissions(self):
        self.assertFalse(any(name.startswith('integracoes_') for name in connection.introspection.table_names()))
        self.assertFalse(ContentType.objects.filter(app_label='integracoes').exists())
        self.assertFalse(Permission.objects.filter(content_type__app_label='integracoes').exists())

    def test_existing_database_removes_module_data_and_preserves_bookings_users_and_history(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate([('agenda', '0016_agenda_visita_local')])
        try:
            user = get_user_model().objects.create_user('autor-preservado')
            group = Group.objects.create(name='Grupo preservado')
            user.groups.add(group)
            start = datetime(2099, 1, 10, 12, tzinfo=timezone.utc)
            common = dict(criado_por=user, versao=3, cancelado_em=start, situacao='confirmado')
            bookings = [
                AgendaServico.objects.create(servico=Servico.objects.create(nome='Serviço preservado'),
                    motivo='Legado', inicio=start, fim=start + timedelta(hours=1), **common),
                AgendaEquipamento.objects.create(equipamento=Equipamento.objects.create(nome='Máquina preservada'),
                    motivo='Legado', inicio=start, fim=start + timedelta(hours=1), **common),
                AgendaVisita.objects.create(quantidade_pessoas=2, data=start.date(),
                    hora_inicio='09:00', hora_termino='10:00', **common),
            ]
            for booking in bookings:
                EventoAgendamento.objects.create(**{'agenda_' + booking.categoria: booking},
                    ator=user, ator_nome='Origem histórica', acao='criar', alteracoes={'legado': True})
            snapshots = {model: list(model.objects.values()) for model in
                         (AgendaServico, AgendaEquipamento, AgendaVisita, EventoAgendamento)}
            self.create_retired_tables(AgendaServico._meta.db_table)
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO integracoes_pedidointegracao VALUES (1, 1, %s)', [bookings[0].pk])
            content_type = ContentType.objects.create(app_label='integracoes', model='clienteintegracao')
            old_permission = Permission.objects.create(content_type=content_type, codename='view_clienteintegracao', name='Antiga')
            user.user_permissions.add(old_permission)
            group.permissions.add(old_permission)
            kept_permission = Permission.objects.get(content_type__app_label='agenda', codename='view_agendaservico')
            user.user_permissions.add(kept_permission)
            recorder = MigrationRecorder(connection)
            recorder.record_applied('integracoes', '0001_initial')
            recorder.record_applied('integracoes', '0003_finaliza_agendas_tipadas')

            MigrationExecutor(connection).migrate(latest)

            self.assertFalse(any(name.startswith('integracoes_') for name in connection.introspection.table_names()))
            self.assertFalse(ContentType.objects.filter(app_label='integracoes').exists())
            self.assertFalse(Permission.objects.filter(pk=old_permission.pk).exists())
            self.assertFalse(recorder.migration_qs.filter(app='integracoes').exists())
            self.assertEqual(list(user.user_permissions.values_list('pk', flat=True)), [kept_permission.pk])
            self.assertTrue(user.groups.filter(pk=group.pk).exists())
            self.assertFalse(group.permissions.exists())
            for model, rows in snapshots.items():
                self.assertEqual(list(model.objects.values()), rows)
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_upgrade_before_agenda_split_removes_legacy_foreign_keys_and_keeps_local_booking(self):
        previous = [('agenda', '0012_identifica_reservas_recebidas_agrohub'), ('catalogo', '0007_remove_espaco')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            service = apps.get_model('catalogo', 'Servico').objects.create(nome='Serviço antigo')
            booking = apps.get_model('agenda', 'Agendamento').objects.create(servico=service, motivo='Preservar',
                inicio='2099-01-10T12:00:00Z', fim='2099-01-10T13:00:00Z', versao=4)
            apps.get_model('agenda', 'EventoAgendamento').objects.create(agendamento=booking,
                ator_nome='Origem histórica', acao='criar', alteracoes={'motivo': {'novo': 'Preservar'}})
            self.create_retired_tables('agenda_agendamento')
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO integracoes_pedidointegracao VALUES (1, 1, %s)', [booking.pk])
            MigrationExecutor(connection).migrate(latest)
            saved = AgendaServico.objects.get(pk=booking.pk)
            self.assertEqual((saved.motivo, saved.versao), ('Preservar', 4))
            self.assertEqual(saved.eventos.get().ator_nome, 'Origem histórica')
            self.assertNotIn('agenda_agendamento', connection.introspection.table_names())
            self.assertNotIn('integracoes_pedidointegracao', connection.introspection.table_names())
        finally:
            MigrationExecutor(connection).migrate(latest)
