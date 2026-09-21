"""Neutral terminal interface, with no MCP and no business rules."""

import argparse
import json
import sys
from pathlib import Path

from app.database import get_schema, query_sql
from app.sql_policy import QueryError


def main():
    parser = argparse.ArgumentParser(description="Read-only T-SQL access to the demo database")
    sub = parser.add_subparsers(dest="command", required=True)
    schema = sub.add_parser("schema", help="Inspect columns and relationships")
    schema.add_argument("--schema")
    query = sub.add_parser("query", help="Execute a SELECT from a UTF-8 file or stdin")
    query.add_argument("--file", type=Path, help="Otherwise reads SQL from stdin")
    args = parser.parse_args()
    try:
        if args.command == "schema":
            result = get_schema(args.schema)
        else:
            sql = args.file.read_text(encoding="utf-8-sig") if args.file else sys.stdin.read()
            result = query_sql(sql)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    except QueryError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
