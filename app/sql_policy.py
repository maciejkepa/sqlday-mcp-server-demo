"""A deliberately narrow T-SQL surface; database permissions remain the security boundary."""

import logging

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, SqlglotError
from sqlglot.optimizer.scope import traverse_scope

ALLOWED_OBJECTS = frozenset(
    name.lower()
    for name in (
        "SalesLT.Customer",
        "SalesLT.Address",
        "SalesLT.CustomerAddress",
        "SalesLT.Product",
        "SalesLT.ProductCategory",
        "SalesLT.SalesOrderHeader",
        "SalesLT.SalesOrderDetail",
        "Ops.OrderFlags",
        "Ops.OrderEvent",
        "CRM.CustomerIdentity",
        "Integration.CountryAlias",
        "Catalog.ProductClassification",
        "Reporting.SalesSummary",
    )
)
ALLOWED_SCHEMAS = frozenset(name.split(".")[0] for name in ALLOWED_OBJECTS)
MAX_SQL_CHARS = 20_000
# SQLGlot's unsupported-syntax warnings include raw SQL. Return our safe errors instead.
logging.getLogger("sqlglot").disabled = True


class QueryError(ValueError):
    """A safe, user-facing query/configuration error."""


def validate_sql(sql: str) -> str:
    if not sql.strip() or len(sql) > MAX_SQL_CHARS:
        raise QueryError("Provide a nonempty SELECT of at most 20000 characters.")
    try:
        statements = sqlglot.parse(sql, read="tsql", error_level=ErrorLevel.RAISE)
        if len(statements) != 1 or not isinstance(
            statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)
        ):
            raise QueryError("Only one SELECT query (including CTEs) is allowed.")
        tree = statements[0]
        forbidden = (
            exp.DDL,
            exp.DML,
            exp.Command,
            exp.Into,
            exp.Lock,
            exp.Dot,
            exp.Anonymous,
            exp.Parameter,
            exp.Placeholder,
            exp.NextValueFor,
        )
        if any(isinstance(node, forbidden) for node in tree.walk()):
            raise QueryError(
                "Writes, commands, variables and custom/external functions are disabled."
            )
        # Validate actual table sources, not CTE aliases. This also handles nested CTE scopes.
        for scope in traverse_scope(tree):
            for source in scope.sources.values():
                if not isinstance(source, exp.Table):
                    continue
                if not isinstance(source.this, exp.Identifier) or source.catalog:
                    raise QueryError("External sources and cross-database queries are disabled.")
                name = f"{source.db}.{source.name}".lower()
                if name not in ALLOWED_OBJECTS:
                    raise QueryError("Use an allowed, schema-qualified object from get_schema.")
        # Catch table-valued functions even when the scope represents them as a derived source.
        for table in tree.find_all(exp.Table):
            if not isinstance(table.this, exp.Identifier) or table.catalog:
                raise QueryError("External sources and table-valued functions are disabled.")
        return sql
    except QueryError:
        raise
    except (SqlglotError, ValueError, TypeError, RecursionError):
        raise QueryError(
            "Cannot validate this T-SQL. Simplify it to a single SELECT with CTEs."
        ) from None
