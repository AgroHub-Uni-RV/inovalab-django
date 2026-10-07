"""Read-only checks before adopting the standalone laboratory's tables."""
from django.apps import apps
from django.db.migrations.recorder import MigrationRecorder
from django.db import models
from importlib.resources import files
import json
from inovalab_app import schema_checks

LEGACY_LEAVES = {
    'catalogo': '0007_remove_espaco', 'materiais': '0001_initial',
    'tarefas': '0001_initial', 'conteudo': '0001_initial',
    'agenda': '0017_remove_integracoes',
}
LEGACY_CONTENT_TYPES = {
    'servico': 'catalogo', 'equipamento': 'catalogo', 'material': 'materiais',
    'tarefa': 'tarefas', 'eventotarefa': 'tarefas', 'banner': 'conteudo',
    'agendaservico': 'agenda', 'agendaequipamento': 'agenda',
    'agendavisita': 'agenda', 'eventoagendamento': 'agenda',
}


class UpgradeError(RuntimeError):
    pass


def _type_family(name):
    return {
        'BigAutoField': 'BigIntegerField', 'PositiveBigIntegerField': 'BigIntegerField',
        'AutoField': 'IntegerField', 'PositiveIntegerField': 'IntegerField',
        'PositiveSmallIntegerField': 'SmallIntegerField', 'SmallAutoField': 'SmallIntegerField',
        'ImageField': 'CharField', 'FileField': 'CharField', 'SlugField': 'CharField',
    }.get(name, name)


def business_models():
    config = apps.get_app_config('inovalab_app')
    return list(config.get_models(include_auto_created=True))


def validate_content_types(connection):
    if 'django_content_type' not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT app_label, model FROM django_content_type')
        keys = set(cursor.fetchall())
    for model, old_label in LEGACY_CONTENT_TYPES.items():
        if (old_label, model) in keys and ('inovalab_app', model) in keys:
            raise UpgradeError(f'ContentType conflitante: {old_label}.{model} / inovalab_app.{model}.')


def validate_existing_schema(connection):
    """Return False for an empty installation, True for a compatible existing DB."""
    models_to_check = business_models()
    expected_tables = {model._meta.db_table for model in models_to_check}
    actual_tables = set(connection.introspection.table_names())
    applied = set(MigrationRecorder(connection).applied_migrations())
    historical = {(app, name) for app, name in applied if app in LEGACY_LEAVES}
    present = expected_tables & actual_tables
    if not present and not historical:
        return False
    missing = expected_tables - actual_tables
    if missing:
        raise UpgradeError('Tabelas ausentes: '+', '.join(sorted(missing)))
    if ('inovalab_app', '0001_initial') not in applied:
        pending = [(app, name) for app, name in LEGACY_LEAVES.items() if (app, name) not in applied]
        if pending:
            raise UpgradeError('Atualize primeiro as migrações da versão anterior: '+', '.join(f'{app}.{name}' for app, name in pending))
    retired = {'catalogo_espaco', 'agenda_agendamento', 'agenda_reservaagrohub',
               'agenda_controleagendavisitas', 'integracoes_clienteintegracao', 'integracoes_pedidointegracao'} & actual_tables
    if retired:
        raise UpgradeError('Tabelas legadas ainda presentes: '+', '.join(sorted(retired)))
    with connection.cursor() as cursor:
        baseline_checks = json.loads(files('inovalab_app').joinpath('baseline_checks.json').read_text(encoding='utf-8')).get(connection.vendor)
        if baseline_checks is None:
            raise UpgradeError('A consolidação suporta somente SQLite e PostgreSQL.')
        for model in models_to_check:
            table = model._meta.db_table
            columns = {field.name: field for field in connection.introspection.get_table_description(cursor, table)}
            constraints = connection.introspection.get_constraints(cursor, table)
            expected_columns = {field.column for field in model._meta.local_fields}
            if expected_columns != set(columns):
                raise UpgradeError(f'{table}: colunas divergentes: '+', '.join(sorted(expected_columns ^ set(columns))))
            for field in model._meta.local_fields:
                column = columns[field.column]
                db_field = field.target_field if field.is_relation else field
                expected_type = _type_family(db_field.get_internal_type())
                actual_type = _type_family(connection.introspection.get_field_type(column.type_code, column))
                # SQLite stores all integer widths as INTEGER.
                integer_width = connection.vendor == 'sqlite' and expected_type.endswith('IntegerField') and actual_type.endswith('IntegerField')
                if actual_type != expected_type and not integer_width:
                    raise UpgradeError(f'{table}.{field.column}: tipo divergente ({actual_type}, esperado {expected_type}).')
                if bool(column.null_ok) != bool(field.null):
                    raise UpgradeError(f'{table}.{field.column}: nulabilidade divergente.')
                if expected_type == 'CharField':
                    length = column.internal_size if connection.vendor == 'postgresql' else column.display_size
                    if length is not None and length != db_field.max_length:
                        raise UpgradeError(f'{table}.{field.column}: tamanho divergente.')
                # SQLite's decimal affinity has no enforced precision/scale.
                if expected_type == 'DecimalField' and connection.vendor != 'sqlite':
                    if (column.precision, column.scale) != (db_field.max_digits, db_field.decimal_places):
                        raise UpgradeError(f'{table}.{field.column}: precisão decimal divergente.')
                entries = [entry for entry in constraints.values() if entry['columns'] == [field.column]]
                if field.primary_key and not any(entry.get('primary_key') for entry in entries):
                    raise UpgradeError(f'{table}.{field.column}: chave primária ausente.')
                if field.unique and not field.primary_key and not any(entry.get('unique') for entry in entries):
                    raise UpgradeError(f'{table}.{field.column}: unicidade ausente.')
                if field.is_relation and field.db_constraint:
                    target = (field.target_field.model._meta.db_table, field.target_field.column)
                    if not any(entry.get('foreign_key') == target for entry in entries):
                        raise UpgradeError(f'{table}.{field.column}: chave estrangeira divergente.')
                if field.db_index and not field.unique and not any(entry.get('index') for entry in entries):
                    raise UpgradeError(f'{table}.{field.column}: índice ausente.')
            check_names = {item.name for item in model._meta.constraints if isinstance(item, models.CheckConstraint)}
            definitions = schema_checks.check_definitions(connection, cursor, table, check_names)
            for constraint in model._meta.constraints:
                entry = constraints.get(constraint.name)
                kind = 'check' if isinstance(constraint, models.CheckConstraint) else 'unique'
                if not entry or not entry.get(kind):
                    raise UpgradeError(f'{table}: restrição ausente: {constraint.name}.')
                if kind == 'check' and definitions.get(constraint.name) != baseline_checks.get(constraint.name):
                    raise UpgradeError(f'{table}: definição divergente: {constraint.name}.')
            for index in model._meta.indexes:
                entry = constraints.get(index.name)
                expected = [model._meta.get_field(name.lstrip('-')).column for name in index.fields]
                if not entry or not entry.get('index') or entry['columns'] != expected:
                    raise UpgradeError(f'{table}: índice divergente: {index.name}.')
            for fields in model._meta.unique_together:
                expected = [model._meta.get_field(name).column for name in fields]
                if not any(entry.get('unique') and entry['columns'] == expected for entry in constraints.values()):
                    raise UpgradeError(f'{table}: unicidade composta ausente: {expected}.')
    validate_content_types(connection)
    return True
