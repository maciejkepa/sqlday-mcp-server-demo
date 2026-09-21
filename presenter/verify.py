"""Private numeric gold checks; no expected values are served through MCP."""

from pathlib import Path

from app.database import connection_string, query_sql
from app.sql_policy import QueryError

REFERENCE_DIR = Path(__file__).resolve().parent / "reference"
EXPECTED = {
    "q1": [["3200.0000"]],
    "q2": [["NW-MOBILITY", "2150.0000"]],
    "q3": [["United States", "2150.0000"], ["United Kingdom", "1050.0000"]],
    "q4": [
        ["Bikes", "2650.0000"],
        ["Safety Gear", "300.0000"],
        ["Services", "150.0000"],
        ["Accessories", "100.0000"],
    ],
    "q5": [[3, 6, 3000, "3200.0000"]],
}


def main():
    try:
        connection_string()
    except QueryError as exc:
        print(f"Configuration error: {exc}")
        print(
            "In this terminal, run scripts/Initialize-Secrets.ps1; on first use add -SqlServer <server>.database.windows.net."
        )
        return 1
    failed = False
    for name, expected in EXPECTED.items():
        try:
            result = query_sql((REFERENCE_DIR / f"{name}.sql").read_text(encoding="utf-8"))
            ok = result["rows"] == expected and not result["truncated"]
            print(f"{name}: {'PASS' if ok else 'FAIL'} ({result['elapsed_ms']} ms)")
            if not ok:
                print(f"  Expected {expected}; got {result['rows']}")
            failed |= not ok
        except QueryError as exc:
            print(f"{name}: FAIL: {exc}")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
