"""Compare Django's declared schema with PostgreSQL's installed current schema."""

from uuid import uuid4

from django.db import transaction


def index_signature(cursor, table, name):
    """Describe an index without its schema-local name or temporary table name."""
    cursor.execute(
        "SELECT x.indnkeyatts,x.indisunique,x.indisprimary,x.indisexclusion,"
        "x.indnullsnotdistinct,am.amname,i.reloptions,"
        "ARRAY(SELECT pg_get_indexdef(i.oid,n,true) "
        "FROM generate_series(1,x.indnatts) n),"
        "pg_get_expr(x.indpred,x.indrelid),pg_get_expr(x.indexprs,x.indrelid) "
        "FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid "
        "JOIN pg_am am ON am.oid=i.relam "
        "WHERE x.indrelid=%s::regclass AND i.relname=%s",
        [table, name],
    )
    return cursor.fetchone()


def constraint_definition(cursor, table, name):
    """Return a server-parsed constraint definition, not Python-generated text."""
    cursor.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid=%s::regclass AND conname=%s",
        [table, name],
    )
    result = cursor.fetchone()
    return result[0] if result else None


def assert_model_contract(connection, model):
    """Check fields, implicit keys and parsed named constraint/index definitions.

    Temporary empty tables only parse Django's current declarations. They do not
    recreate an old schema, upgrade existing rows or execute downgrade paths.
    The enclosing transaction drops each scratch table automatically.
    """
    table = model._meta.db_table
    quote = connection.ops.quote_name
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT attname,format_type(atttypid,atttypmod),attnotnull "
            "FROM pg_attribute WHERE attrelid=%s::regclass "
            "AND attnum>0 AND NOT attisdropped",
            [table],
        )
        columns = {name: (kind, required) for name, kind, required in cursor.fetchall()}
        constraints = connection.introspection.get_constraints(cursor, table)
        for field in model._meta.local_concrete_fields:
            expected_type = (
                field.db_type(connection)
                .replace("varchar(", "character varying(")
                .replace(", ", ",")
            )
            # Django emits the GENERATED clause instead of its normal NOT NULL
            # clause; the computed expression owns generated-field nullability.
            required = not field.null and not field.generated
            assert columns[field.column] == (expected_type, required), (
                table,
                field.column,
                columns[field.column],
                (expected_type, required),
            )
            matching = [
                item
                for item in constraints.values()
                if item["columns"] == [field.column]
            ]
            if field.unique:
                assert any(item["unique"] for item in matching), (table, field.column)
            if field.primary_key:
                assert any(item["primary_key"] for item in matching)
            if field.db_index:
                assert any(item["index"] or item["unique"] for item in matching), (
                    table,
                    field.column,
                    "declared field index",
                )
            if field.is_relation and field.db_constraint:
                target = field.target_field
                assert any(
                    item["foreign_key"] == (target.model._meta.db_table, target.column)
                    for item in matching
                ), (table, field.column)
        assert set(columns) == {
            field.column for field in model._meta.local_concrete_fields
        }
        scratch = "schema_contract_" + uuid4().hex
        cursor.execute(
            f"CREATE TEMP TABLE {quote(scratch)} "
            f"(LIKE {quote(table)} INCLUDING DEFAULTS INCLUDING GENERATED) "
            "ON COMMIT DROP"
        )
        with connection.schema_editor(collect_sql=True) as editor:
            for field in model._meta.local_concrete_fields:
                if not field.has_db_default():
                    continue
                default, params = editor.db_default_sql(field)
                cursor.execute(
                    f"ALTER TABLE {quote(scratch)} ALTER COLUMN "
                    f"{quote(field.column)} SET DEFAULT {default}",
                    params,
                )
                cursor.execute(
                    "SELECT pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a "
                    "LEFT JOIN pg_attrdef d ON a.attrelid=d.adrelid AND a.attnum=d.adnum "
                    "WHERE a.attrelid IN (%s::regclass,%s::regclass) AND a.attname=%s "
                    "ORDER BY a.attrelid",
                    [table, scratch, field.column],
                )
                defaults = cursor.fetchall()
                assert len(defaults) == 2 and defaults[0] == defaults[1], (
                    table,
                    field.column,
                    "declared database default",
                    defaults,
                )
            for item in [*model._meta.constraints, *model._meta.indexes]:
                statement = item.create_sql(model, editor)
                assert statement is not None, (table, item.name)
                cursor.execute(str(statement).replace(quote(table), quote(scratch)))
                # Baseline SQL has undergone pg_dump/deparse once. Reparse the
                # expected definition too, so PostgreSQL performs the same exact
                # literal-array cast normalization on both sides.
                definition = constraint_definition(cursor, scratch, item.name)
                if definition is not None:
                    cursor.execute(
                        f"ALTER TABLE {quote(scratch)} "
                        f"DROP CONSTRAINT {quote(item.name)}"
                    )
                    cursor.execute(
                        f"ALTER TABLE {quote(scratch)} ADD CONSTRAINT "
                        f"{quote(item.name)} {definition}"
                    )
                    assert constraint_definition(
                        cursor, table, item.name
                    ) == constraint_definition(cursor, scratch, item.name), (
                        table,
                        item.name,
                    )
                else:
                    cursor.execute(
                        "SELECT pg_get_indexdef(indexrelid) FROM pg_index "
                        "JOIN pg_class i ON i.oid=indexrelid "
                        "WHERE indrelid=%s::regclass AND i.relname=%s",
                        [scratch, item.name],
                    )
                    definition = cursor.fetchone()[0]
                    cursor.execute(f"DROP INDEX pg_temp.{quote(item.name)}")
                    cursor.execute(definition)
                    assert index_signature(cursor, table, item.name) == index_signature(
                        cursor, scratch, item.name
                    ), (table, item.name)
