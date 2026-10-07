"""Compatibilidade de bancos anteriores à retirada do app de integradores."""


def remove_retired_tables(schema_editor):
    tables = set(schema_editor.connection.introspection.table_names())
    # O pedido depende do cliente e pode apontar para a agenda legada ou tipada.
    for name in ('integracoes_pedidointegracao', 'integracoes_clienteintegracao'):
        if name in tables:
            schema_editor.execute(f'DROP TABLE {schema_editor.quote_name(name)}')
