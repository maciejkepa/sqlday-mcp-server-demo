"""SQL connections, schema metadata and bounded query results."""

import json
import os
from contextlib import closing
from datetime import date, datetime, time
from decimal import Decimal
from time import perf_counter

import pyodbc

from app.sql_policy import ALLOWED_OBJECTS, ALLOWED_SCHEMAS, QueryError, validate_sql

DATABASE_NAME = "AdventureWorksLT_MCPDemo"
QUERY_TIMEOUT = 15
MAX_ROWS = 200
MAX_BYTES = 64 * 1024


def odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def connection_string() -> str:
    names = ("AW_SQL_SERVER", "AW_SQL_USER", "AW_SQL_PASSWORD")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise QueryError("SQL is not configured. Missing: " + ", ".join(missing) + ".")
    database = os.environ.get("AW_SQL_DATABASE", DATABASE_NAME)
    if database != DATABASE_NAME:
        raise QueryError(f"This demo connects only to {DATABASE_NAME}.")
    fields = {
        "DRIVER": "ODBC Driver 18 for SQL Server",
        "SERVER": os.environ["AW_SQL_SERVER"],
        "DATABASE": database,
        "UID": os.environ["AW_SQL_USER"],
        "PWD": os.environ["AW_SQL_PASSWORD"],
        "Encrypt": "yes",
        "TrustServerCertificate": "no",
        "APP": "SQLDay MCP Demo",
    }
    return ";".join(f"{key}={odbc_value(value)}" for key, value in fields.items())


def connect():
    conn = pyodbc.connect(connection_string(), timeout=5, autocommit=True)
    conn.timeout = QUERY_TIMEOUT
    return conn


def safe_sql_error(exc: pyodbc.Error) -> QueryError:
    # Never return the driver message: it can include SQL literals, hosts or credentials.
    state = str(exc.args[0]) if exc.args else ""
    if state in {"HYT00", "HYT01"}:
        return QueryError(
            "SQL_TIMEOUT: query exceeded its time limit. Filter or simplify the query."
        )
    if state.startswith("08") or state in {"28000", "IM002", "IM003"}:
        return QueryError(
            "SQL_UNAVAILABLE: check connectivity, ODBC Driver 18 and reader credentials."
        )
    if state.startswith("42"):
        return QueryError(
            "SQL_INVALID: check T-SQL syntax, column names and permissions with get_schema."
        )
    if state.startswith("22"):
        return QueryError("SQL_DATA_ERROR: check conversions, arithmetic and date types.")
    return QueryError(
        "SQL_FAILED: the database rejected the query; simplify it and inspect the schema."
    )


def json_value(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def json_size(value) -> int:
    # Default separators are conservative relative to the SDK's compact serialization.
    return len(json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8"))


def read_result(cursor, started: float) -> dict:
    result = {
        "columns": [column[0] for column in cursor.description],
        "rows": [],
        "row_count": 0,
        "elapsed_ms": 0,
        "truncated": False,
        "truncation_reason": None,
    }
    # Leave space for final metadata. The bound applies to this JSON result, not MCP envelopes.
    if json_size(result) > MAX_BYTES - 256:
        raise QueryError("Result column metadata exceeds 64 KiB. Select fewer columns.")
    for index in range(MAX_ROWS + 1):
        row = cursor.fetchone()
        if row is None:
            break
        if index == MAX_ROWS:
            result.update(truncated=True, truncation_reason="row_limit")
            break
        converted = [json_value(value) for value in row]
        result["rows"].append(converted)
        if json_size(result) > MAX_BYTES - 256:
            result["rows"].pop()
            result.update(truncated=True, truncation_reason="byte_limit")
            break
    result["row_count"] = len(result["rows"])
    result["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
    return result


def query_sql(sql: str) -> dict:
    validate_sql(sql)
    started = perf_counter()
    try:
        with closing(connect()) as conn, closing(conn.cursor()) as cursor:
            cursor.execute(sql)
            if not cursor.description:
                raise QueryError("The query must return a tabular result.")
            return read_result(cursor, started)
    except pyodbc.Error as exc:
        raise safe_sql_error(exc) from None


COLUMNS_SQL = """
SELECT s.name, o.name, o.type_desc, c.name, t.name, c.max_length,
       c.precision, c.scale, c.is_nullable, c.column_id,
       COALESCE(pk.key_ordinal, 0) AS pk_ordinal
FROM sys.objects AS o
JOIN sys.schemas AS s ON s.schema_id = o.schema_id
JOIN sys.columns AS c ON c.object_id = o.object_id
JOIN sys.types AS t ON t.user_type_id = c.user_type_id
LEFT JOIN (
    SELECT i.object_id, ic.column_id, ic.key_ordinal
    FROM sys.indexes AS i
    JOIN sys.index_columns AS ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
    WHERE i.is_primary_key=1
) AS pk ON pk.object_id=c.object_id AND pk.column_id=c.column_id
WHERE o.type IN ('U', 'V') AND (? IS NULL OR s.name=?)
ORDER BY s.name, o.name, c.column_id
"""
FOREIGN_KEYS_SQL = """
SELECT s.name, o.name, fk.name, c.name, rs.name, ro.name, rc.name, fkc.constraint_column_id
FROM sys.foreign_keys AS fk
JOIN sys.foreign_key_columns AS fkc ON fkc.constraint_object_id=fk.object_id
JOIN sys.objects AS o ON o.object_id=fkc.parent_object_id
JOIN sys.schemas AS s ON s.schema_id=o.schema_id
JOIN sys.columns AS c ON c.object_id=o.object_id AND c.column_id=fkc.parent_column_id
JOIN sys.objects AS ro ON ro.object_id=fkc.referenced_object_id
JOIN sys.schemas AS rs ON rs.schema_id=ro.schema_id
JOIN sys.columns AS rc ON rc.object_id=ro.object_id AND rc.column_id=fkc.referenced_column_id
ORDER BY s.name, o.name, fk.name, fkc.constraint_column_id
"""


def get_schema(schema: str | None = None) -> dict:
    if schema is not None and schema.lower() not in ALLOWED_SCHEMAS:
        raise QueryError(
            "Unknown schema. Call get_schema without a filter to list available objects."
        )
    objects = {}
    try:
        with closing(connect()) as conn, closing(conn.cursor()) as cursor:
            for row in cursor.execute(COLUMNS_SQL, schema, schema).fetchall():
                key = f"{row[0]}.{row[1]}"
                if key.lower() not in ALLOWED_OBJECTS:
                    continue
                obj = objects.setdefault(
                    key, {"name": key, "kind": row[2], "columns": [], "foreign_keys": []}
                )
                obj["columns"].append(
                    dict(
                        zip(
                            (
                                "name",
                                "type",
                                "max_length_bytes",
                                "precision",
                                "scale",
                                "nullable",
                                "ordinal",
                                "primary_key_ordinal",
                            ),
                            row[3:],
                            strict=True,
                        )
                    )
                )
            for row in cursor.execute(FOREIGN_KEYS_SQL).fetchall():
                key, target = f"{row[0]}.{row[1]}", f"{row[4]}.{row[5]}"
                if key in objects and target.lower() in ALLOWED_OBJECTS:
                    objects[key]["foreign_keys"].append(
                        {
                            "name": row[2],
                            "column": row[3],
                            "references": target,
                            "referenced_column": row[6],
                            "ordinal": row[7],
                        }
                    )
        return {"dialect": "T-SQL", "database": DATABASE_NAME, "objects": list(objects.values())}
    except pyodbc.Error as exc:
        raise safe_sql_error(exc) from None
