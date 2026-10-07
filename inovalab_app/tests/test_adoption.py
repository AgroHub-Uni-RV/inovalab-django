from datetime import date, datetime, time, timezone
from importlib import import_module
from io import StringIO
from django.apps import apps
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from inovalab_app.models import (AgendaEquipamento, AgendaServico, AgendaVisita, Banner, Equipamento,
                                EventoAgendamento, EventoTarefa, Material, Servico, Tarefa)
from inovalab_app.upgrade import LEGACY_CONTENT_TYPES, LEGACY_LEAVES


class ExistingDatabaseAdoptionTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        call_command('seed_inovalab', stdout=StringIO())
        self.applied_before = set(MigrationRecorder(connection).applied_migrations())

    def tearDown(self):
        recorder = MigrationRecorder(connection)
        for app, name in set(recorder.applied_migrations()) - self.applied_before:
            recorder.record_unapplied(app, name)
        for app, name in self.applied_before - set(recorder.applied_migrations()):
            recorder.record_applied(app, name)
        for model, old_label in LEGACY_CONTENT_TYPES.items():
            # Flush removes all ContentTypes after tearDown; no production rollback.
            if ContentType.objects.filter(app_label='inovalab_app', model=model).exists():
                ContentType.objects.filter(app_label=old_label, model=model).delete()
            else:
                ContentType.objects.filter(app_label=old_label, model=model).update(app_label='inovalab_app')
        ContentType.objects.clear_cache()
        super().tearDown()
    def test_adoption_preserves_data_m2m_microseconds_permissions_and_admin_history(self):
        actor = get_user_model().objects.create_user('autor-consolidacao')
        service = Servico.objects.first()
        machine = Equipamento.objects.first()
        material = Material.objects.create(nome='PLA', categoria='Filamento', quantidade='12.125', unidade='g', fonte='Lab')
        instant = datetime(2026, 11, 1, 14, 0, 37, 123456, tzinfo=timezone.utc)
        end = instant.replace(hour=15, second=41, microsecond=654321)
        task = Tarefa.objects.create(servico=service, responsavel=actor, descricao='Preservar', prazo=instant, versao=7)
        EventoTarefa.objects.create(tarefa=task, ator=actor, ator_nome='Histórico', acao='criar', status_novo='demanda', alteracoes={'campo': {'novo': 'valor'}})
        booking = AgendaServico.objects.create(servico=service, inicio=instant, fim=end, motivo='Protótipo', criado_por=actor,
                                              avaliado_por=actor, material_gasto=material, material_proprio=False, material_gasto_gramas='0.125')
        booking.equipamentos.add(machine)
        AgendaEquipamento.objects.create(equipamento=machine, inicio=instant, fim=end, criado_por=actor, motivo='Máquina')
        AgendaVisita.objects.create(quantidade_pessoas=4, data=date(2026, 11, 2), hora_inicio=time(9, 0, 37, 123456),
                                   hora_termino=time(10, 0, 41, 654321), criado_por=actor)
        EventoAgendamento.objects.create(agenda_servico=booking, ator=actor, ator_nome='Autor', acao='criar')
        Banner.objects.create(titulo='Banner preservado', banner_img='banners/preservado.webp')
        ct = ContentType.objects.get_for_model(Servico)
        permission = Permission.objects.get(content_type=ct, codename='change_servico')
        group = Group.objects.create(name='Permissão preservada')
        group.permissions.add(permission)
        actor.user_permissions.add(permission)
        actor.groups.add(group)
        log = LogEntry.objects.log_actions(user_id=actor.pk, queryset=Servico.objects.filter(pk=service.pk), action_flag=ADDITION)[0]
        table_names = [model._meta.db_table for model in apps.get_app_config('inovalab_app').get_models(include_auto_created=True)]
        table_names += ['auth_permission', 'auth_group_permissions', get_user_model()._meta.db_table+'_user_permissions',
                        get_user_model()._meta.db_table+'_groups', 'django_admin_log']
        def rows():
            snapshot = {}
            with connection.cursor() as cursor:
                for table in table_names:
                    cursor.execute('SELECT * FROM '+connection.ops.quote_name(table)+' ORDER BY id')
                    snapshot[table] = cursor.fetchall()
            return snapshot
        before = rows()
        for model, old_label in LEGACY_CONTENT_TYPES.items():
            ContentType.objects.filter(app_label='inovalab_app', model=model).update(app_label=old_label)
        ContentType.objects.clear_cache()
        recorder = MigrationRecorder(connection)
        recorder.record_unapplied('inovalab_app', '0002_preserva_contenttypes')
        recorder.record_unapplied('inovalab_app', '0001_initial')
        for label, migration in LEGACY_LEAVES.items():
            recorder.record_applied(label, migration)
        try:
            call_command('migrate', fake_initial=True, interactive=False, stdout=StringIO(), verbosity=0)
            self.assertEqual(rows(), before)
            ct.refresh_from_db()
            self.assertEqual(ct.app_label, 'inovalab_app')
            self.assertEqual(log.content_type_id, ct.pk)
            self.assertEqual(group.permissions.get().pk, permission.pk)
            self.assertEqual(actor.user_permissions.get().pk, permission.pk)
            self.assertTrue(set(LEGACY_LEAVES.items()).issubset(recorder.applied_migrations()))
        finally:
            ContentType.objects.clear_cache()

    def test_content_type_collision_aborts_before_initial_is_recorded(self):
        ContentType.objects.create(app_label='catalogo', model='servico')
        recorder = MigrationRecorder(connection)
        recorder.record_unapplied('inovalab_app', '0002_preserva_contenttypes')
        recorder.record_unapplied('inovalab_app', '0001_initial')
        for label, migration in LEGACY_LEAVES.items():
            recorder.record_applied(label, migration)
        with self.assertRaisesMessage(Exception, 'ContentType conflitante'):
            call_command('migrate', fake_initial=True, interactive=False, stdout=StringIO())
        self.assertNotIn(('inovalab_app', '0001_initial'), recorder.applied_migrations())

    def test_migration_itself_checks_all_collisions_before_changing_labels(self):
        for model, old_label in LEGACY_CONTENT_TYPES.items():
            ContentType.objects.filter(app_label='inovalab_app', model=model).update(app_label=old_label)
        ContentType.objects.create(app_label='inovalab_app', model='eventoagendamento')
        migration = import_module('inovalab_app.migrations.0002_preserva_contenttypes')
        with connection.schema_editor(atomic=False) as editor:
            with self.assertRaisesMessage(RuntimeError, 'ContentType conflitante'):
                migration.preserve_content_types(apps, editor)
        self.assertTrue(ContentType.objects.filter(app_label='catalogo', model='servico').exists())
