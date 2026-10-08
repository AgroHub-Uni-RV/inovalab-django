from io import StringIO
from unittest.mock import patch
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase
from inovalab_app.upgrade import validate_existing_schema, UpgradeError, LEGACY_LEAVES, business_models
from inovalab_app import schema_checks


class SchemaValidationTests(TestCase):
    def test_installed_sqlite_schema_accepts_django52_boolean_checks(self):
        if connection.vendor != 'sqlite':
            self.skipTest('Representação específica de booleanos no SQLite.')
        original = schema_checks.check_definitions
        def definitions(*args):
            return {name: value.replace('material_proprio = 1', 'material_proprio').replace('material_proprio = 0', 'NOT material_proprio')
                    for name, value in original(*args).items()}
        with patch.object(schema_checks, 'check_definitions', side_effect=definitions):
            self.assertTrue(validate_existing_schema(connection))

    def test_complete_current_schema_is_valid(self):
        self.assertTrue(validate_existing_schema(connection))

    def test_legacy_adoption_requires_original_boolean_checks(self):
        if connection.vendor != 'sqlite':
            self.skipTest('Representação específica de booleanos no SQLite.')
        recorder = MigrationRecorder(connection)
        recorder.record_unapplied('inovalab_app', '0001_initial')
        for app, name in LEGACY_LEAVES.items():
            recorder.record_applied(app, name)
        original = schema_checks.check_definitions
        def definitions(*args):
            return {name: value.replace('material_proprio = 1', 'material_proprio').replace('material_proprio = 0', 'NOT material_proprio')
                    for name, value in original(*args).items()}
        with patch('inovalab_app.upgrade.business_models', return_value=business_models()), patch.object(schema_checks, 'check_definitions', side_effect=definitions):
            with self.assertRaisesMessage(UpgradeError, 'definição divergente'):
                validate_existing_schema(connection)

    def test_missing_table_blocks_adoption(self):
        original = connection.introspection.table_names
        with patch.object(connection.introspection, 'table_names', side_effect=lambda *a, **kw: [name for name in original(*a, **kw) if name != 'materiais_material']):
            with self.assertRaisesMessage(UpgradeError, 'materiais_material'):
                validate_existing_schema(connection)

    def test_missing_column_blocks_adoption(self):
        original = connection.introspection.get_table_description
        def description(cursor, table):
            values = original(cursor, table)
            return [field for field in values if field.name != 'observacoes'] if table == 'agenda_agendavisita' else values
        with patch.object(connection.introspection, 'get_table_description', side_effect=description):
            with self.assertRaisesMessage(UpgradeError, 'observacoes'):
                validate_existing_schema(connection)

    def test_missing_check_constraint_blocks_adoption(self):
        original = connection.introspection.get_constraints
        def constraints(cursor, table):
            values = original(cursor, table)
            values.pop('agendavisita_periodo_positivo', None)
            return values
        with patch.object(connection.introspection, 'get_constraints', side_effect=constraints):
            with self.assertRaisesMessage(UpgradeError, 'agendavisita_periodo_positivo'):
                validate_existing_schema(connection)

    def test_wrong_foreign_key_blocks_adoption(self):
        original = connection.introspection.get_constraints
        def constraints(cursor, table):
            values = original(cursor, table)
            if table == 'tarefas_tarefa':
                for entry in values.values():
                    if entry.get('foreign_key') and entry['columns'] == ['responsavel_id']:
                        entry['foreign_key'] = ('wrong_user', 'id')
            return values
        with patch.object(connection.introspection, 'get_constraints', side_effect=constraints):
            with self.assertRaisesMessage(UpgradeError, 'responsavel_id'):
                validate_existing_schema(connection)

    def test_changed_check_expression_with_same_name_blocks_adoption(self):
        original = schema_checks.check_definitions
        def definitions(*args):
            values = original(*args)
            if 'agendavisita_periodo_positivo' in values:
                values['agendavisita_periodo_positivo'] = values['agendavisita_periodo_positivo'].replace('>', '<')
            return values
        with patch.object(schema_checks, 'check_definitions', side_effect=definitions):
            with self.assertRaisesMessage(UpgradeError, 'definição divergente'):
                validate_existing_schema(connection)

    def test_old_bank_requires_latest_historical_migrations(self):
        recorder = MigrationRecorder(connection)
        recorder.record_unapplied('inovalab_app', '0001_initial')
        with self.assertRaisesMessage(UpgradeError, 'versão anterior'):
            validate_existing_schema(connection)

    def test_command_checks_without_mutating_records(self):
        before = set(MigrationRecorder(connection).applied_migrations())
        call_command('check_inovalab_upgrade', stdout=StringIO())
        self.assertEqual(before, set(MigrationRecorder(connection).applied_migrations()))
