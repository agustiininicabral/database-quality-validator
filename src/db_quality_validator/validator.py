from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_COLUMNS = {
    "customers": {"customer_id", "name", "email"},
    "orders": {"order_id", "customer_id", "order_date", "amount", "status"},
}
ALLOWED_STATUSES = ("completed", "pending", "cancelled")


def create_sample_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
        connection.executescript((ROOT / "sql" / "seed.sql").read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()


def _schema_check(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    results = []
    existing_tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for table, required in REQUIRED_COLUMNS.items():
        if table not in existing_tables:
            results.append({
                "check": f"table_exists:{table}",
                "failures": 1,
                "status": "FAIL",
                "details": f"Required table '{table}' is missing",
            })
            continue
        actual = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        missing = sorted(required - actual)
        results.append({
            "check": f"required_columns:{table}",
            "failures": len(missing),
            "status": "PASS" if not missing else "FAIL",
            "details": "All required columns exist" if not missing else f"Missing columns: {', '.join(missing)}",
        })
    return results


def _count_check(
    connection: sqlite3.Connection, name: str, query: str, details: str
) -> dict[str, Any]:
    failures = int(connection.execute(query).fetchone()[0])
    return {
        "check": name,
        "failures": failures,
        "status": "PASS" if failures == 0 else "FAIL",
        "details": details if failures == 0 else f"{failures} record(s) violate this rule",
    }


def run_checks(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Execute schema and data-quality rules against an open SQLite connection."""
    schema_results = _schema_check(connection)
    schema_invalid = any(item["status"] == "FAIL" for item in schema_results)
    if schema_invalid:
        return schema_results

    queries = [
        ("customer_id_not_null", "SELECT COUNT(*) FROM customers WHERE customer_id IS NULL", "No null customer IDs"),
        ("customer_id_unique", "SELECT COUNT(*) FROM (SELECT customer_id FROM customers GROUP BY customer_id HAVING COUNT(*) > 1)", "Customer IDs are unique"),
        ("customer_name_not_blank", "SELECT COUNT(*) FROM customers WHERE name IS NULL OR trim(name) = ''", "No blank customer names"),
        ("customer_email_not_blank", "SELECT COUNT(*) FROM customers WHERE email IS NULL OR trim(email) = ''", "No blank customer emails"),
        ("customer_email_unique", "SELECT COUNT(*) FROM (SELECT lower(trim(email)) FROM customers GROUP BY lower(trim(email)) HAVING COUNT(*) > 1)", "Customer emails are unique"),
        ("order_id_not_null", "SELECT COUNT(*) FROM orders WHERE order_id IS NULL", "No null order IDs"),
        ("order_id_unique", "SELECT COUNT(*) FROM (SELECT order_id FROM orders GROUP BY order_id HAVING COUNT(*) > 1)", "Order IDs are unique"),
        ("order_customer_exists", "SELECT COUNT(*) FROM orders o LEFT JOIN customers c ON c.customer_id = o.customer_id WHERE c.customer_id IS NULL", "All orders reference existing customers"),
        ("order_amount_positive", "SELECT COUNT(*) FROM orders WHERE amount IS NULL OR amount <= 0", "All order amounts are positive"),
        ("order_date_valid", "SELECT COUNT(*) FROM orders WHERE order_date IS NULL OR date(order_date) IS NULL", "All order dates are valid"),
        ("order_status_allowed", "SELECT COUNT(*) FROM orders WHERE status IS NULL OR status NOT IN ('completed', 'pending', 'cancelled')", "All order statuses are allowed"),
    ]
    results = schema_results
    for name, query, details in queries:
        results.append(_count_check(connection, name, query, details))
    return results


def validate_database(database_path: Path) -> dict[str, Any]:
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")
    connection = sqlite3.connect(database_path)
    try:
        results = run_checks(connection)
    finally:
        connection.close()
    failed = sum(result["status"] == "FAIL" for result in results)
    return {
        "database": str(database_path),
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if failed == 0 else "FAIL",
        "checks_total": len(results),
        "checks_failed": failed,
        "checks_passed": len(results) - failed,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run database quality checks against a SQLite database.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("quality_report.json"))
    parser.add_argument("--create-sample", action="store_true")
    args = parser.parse_args()
    if args.create_sample:
        create_sample_database(args.database)
    report = validate_database(args.database)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
