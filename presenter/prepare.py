"""Prepare only the explicitly named Azure SQL copy, using separate admin credentials."""

import argparse
import os
import re
from contextlib import closing
from pathlib import Path

import pyodbc

from app.database import DATABASE_NAME, odbc_value
from app.sql_policy import ALLOWED_OBJECTS

ROOT = Path(__file__).resolve().parent


def admin_connection_string():
    required = ("AW_SQL_SERVER", "AW_ADMIN_USER", "AW_ADMIN_PASSWORD")
    if any(not os.environ.get(key) for key in required):
        raise ValueError("Set AW_SQL_SERVER, AW_ADMIN_USER and AW_ADMIN_PASSWORD.")
    if os.getenv("AW_SQL_DATABASE", DATABASE_NAME) != DATABASE_NAME:
        raise ValueError("Refusing a non-demo database.")
    values = {
        "DRIVER": "ODBC Driver 18 for SQL Server",
        "SERVER": os.environ["AW_SQL_SERVER"],
        "DATABASE": DATABASE_NAME,
        "UID": os.environ["AW_ADMIN_USER"],
        "PWD": os.environ["AW_ADMIN_PASSWORD"],
        "Encrypt": "yes",
        "TrustServerCertificate": "no",
    }
    return ";".join(f"{k}={odbc_value(v)}" for k, v in values.items())


def sql_batches(text):
    return [
        part.strip()
        for part in re.split(r"^\s*GO\s*$", text, flags=re.MULTILINE | re.IGNORECASE)
        if part.strip()
    ]


def drain(cursor):
    while cursor.nextset():
        pass


def create_reader(cursor):
    password = os.getenv("AW_SQL_PASSWORD", "")
    if not 16 <= len(password) <= 128:
        raise ValueError("Set AW_SQL_PASSWORD to a reader password of 16–128 characters.")
    if os.getenv("AW_SQL_USER", "aw_demo_reader") != "aw_demo_reader":
        raise ValueError("Setup provisions only aw_demo_reader.")
    # Password is a bound parameter; DDL uses SQL Server quoting, never shell interpolation.
    cursor.execute(
        """
        DECLARE @password nvarchar(128) = ?;
        IF EXISTS (SELECT 1 FROM sys.database_role_members
                   WHERE member_principal_id=USER_ID(N'aw_demo_reader'))
            THROW 51006, 'Existing demo reader has role memberships; use a clean demo copy.', 1;
        DECLARE @ddl nvarchar(max);
        IF USER_ID(N'aw_demo_reader') IS NULL
            SET @ddl=N'CREATE USER aw_demo_reader WITH PASSWORD = '+QUOTENAME(@password, '''');
        ELSE
            SET @ddl=N'ALTER USER aw_demo_reader WITH PASSWORD = '+QUOTENAME(@password, '''');
        EXEC sys.sp_executesql @ddl;
        DENY INSERT, UPDATE, DELETE, EXECUTE, ALTER, TAKE OWNERSHIP TO aw_demo_reader;
        DENY CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE FUNCTION,
             CREATE SCHEMA, ALTER ANY USER, ALTER ANY ROLE TO aw_demo_reader;
        DENY IMPERSONATE ON USER::dbo TO aw_demo_reader;
    """,
        password,
    )
    drain(cursor)
    for name in sorted(ALLOWED_OBJECTS):
        schema, table = name.split(".")
        # Names come only from the source-code allowlist, never user input.
        cursor.execute(
            f"GRANT SELECT, VIEW DEFINITION ON OBJECT::[{schema}].[{table}] TO aw_demo_reader"
        )
        drain(cursor)


def main():
    parser = argparse.ArgumentParser(
        description="Reset sales data only in AdventureWorksLT_MCPDemo"
    )
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        required=True,
        help="Explicitly replace sales transactions in the demo copy",
    )
    parser.parse_args()
    phase = "connect"
    try:
        with closing(
            pyodbc.connect(admin_connection_string(), autocommit=False, timeout=10)
        ) as conn:
            conn.timeout = 120
            try:
                with closing(conn.cursor()) as cursor:
                    if cursor.execute("SELECT DB_NAME()").fetchone()[0] != DATABASE_NAME:
                        raise ValueError("Refusing a non-demo database.")
                    cursor.execute(
                        "SET XACT_ABORT ON; SET NOCOUNT ON; SET ANSI_NULLS ON; "
                        "SET QUOTED_IDENTIFIER ON; SET ANSI_WARNINGS ON; "
                        "SET ARITHABORT ON; SET CONCAT_NULL_YIELDS_NULL ON; "
                        "SET NUMERIC_ROUNDABORT OFF;"
                    )
                    drain(cursor)
                    for path in sorted((ROOT / "sql").glob("0*.sql")):
                        for index, batch in enumerate(
                            sql_batches(path.read_text(encoding="utf-8")), 1
                        ):
                            phase = f"{path.name}, batch {index}"
                            cursor.execute(batch)
                            drain(cursor)
                    phase = "reader permissions"
                    create_reader(cursor)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        print("Demo reset committed; reader provisioned. Run presenter.verify next.")
    except pyodbc.Error as exc:
        # Admin failures must not print the DDL containing the reader password.
        print(
            f"Setup rolled back at {phase}. SQLSTATE={str(exc.args[0])[:5]}; "
            f"native codes={re.findall(r'\((\d+)\)', str(exc.args[1:]))}."
        )
        return 1
    except ValueError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
