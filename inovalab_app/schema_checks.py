"""Read constraint definitions without executing schema or data changes."""
import re


def normalize_check(sql):
    # Retain boolean grouping and literal values; ignore formatting and identifier quotes.
    return re.sub(r'\s+', ' ', sql.replace('"', '')).strip()


def check_definitions(connection, cursor, table, names):
    if connection.vendor == 'postgresql':
        cursor.execute('SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint '
                       'WHERE conrelid = %s::regclass AND contype = %s', [connection.ops.quote_name(table), 'c'])
        return {name: normalize_check(definition) for name, definition in cursor.fetchall() if name in names}
    if connection.vendor == 'sqlite':
        cursor.execute('SELECT sql FROM sqlite_master WHERE type = %s AND name = %s', ['table', table])
        row = cursor.fetchone()
        sql = row[0] if row else ''
        definitions = {}
        for name in names:
            match = re.search(r'CONSTRAINT\s+["`\[]?'+re.escape(name)+r'["`\]]?\s+(CHECK\s*\()', sql, flags=re.I)
            if not match:
                continue
            start = match.start(1)
            pos = match.end()-1
            depth, quote = 0, None
            while pos < len(sql):
                char = sql[pos]
                if quote:
                    if char == quote:
                        if pos+1 < len(sql) and sql[pos+1] == quote:
                            pos += 2
                            continue
                        quote = None
                elif char in ("'", '"'):
                    quote = char
                elif char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0:
                        definitions[name] = normalize_check(sql[start:pos+1])
                        break
                pos += 1
        return definitions
    raise RuntimeError('A consolidação suporta somente SQLite e PostgreSQL.')
