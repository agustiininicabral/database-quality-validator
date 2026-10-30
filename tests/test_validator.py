import json
import sqlite3
import sys
from pathlib import Path

import pytest

from db_quality_validator.validator import (
    create_sample_database,
    main,
    run_checks,
    validate_database,
)


def test_clean_sample_database_passes_all_checks(tmp_path):
    database = tmp_path / "sample.sqlite"
    create_sample_database(database)
    report = validate_database(database)
    assert report["status"] == "PASS"
    assert report["checks_failed"] == 0
    assert report["checks_passed"] == 12


def test_validator_detects_data_quality_violations(tmp_path):
    database = tmp_path / "dirty.sqlite"
    create_sample_database(database)
    with sqlite3.connect(database) as con:
        con.execute("INSERT INTO customers VALUES (6, 'Duplicate', 'ANA@example.test')")
        con.execute("INSERT INTO orders VALUES (1009, 999, 'not-a-date', -5, 'unknown')")
        con.execute("INSERT INTO orders VALUES (1009, 1, '2026-02-20', 10, 'completed')")
    report = validate_database(database)
    failures = {row["check"]: row["failures"] for row in report["results"] if row["status"] == "FAIL"}
    assert report["status"] == "FAIL"
    assert failures["customer_email_unique"] == 1
    assert failures["order_id_unique"] == 1
    assert failures["order_customer_exists"] == 1
    assert failures["order_amount_positive"] == 1
    assert failures["order_date_valid"] == 1
    assert failures["order_status_allowed"] == 1


def test_missing_database_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="Database not found"):
        validate_database(tmp_path / "missing.sqlite")


def test_missing_required_tables_are_reported(tmp_path):
    database = tmp_path / "empty.sqlite"
    sqlite3.connect(database).close()
    report = validate_database(database)
    assert report["status"] == "FAIL"
    assert any(item["check"] == "table_exists:customers" for item in report["results"])
    assert report["checks_total"] == 2


def test_missing_required_columns_are_reported(tmp_path):
    database = tmp_path / "partial.sqlite"
    with sqlite3.connect(database) as con:
        con.execute("CREATE TABLE customers (customer_id INTEGER)")
        con.execute("CREATE TABLE orders (order_id INTEGER)")
    report = validate_database(database)
    failed = {item["check"] for item in report["results"] if item["status"] == "FAIL"}
    assert "required_columns:customers" in failed
    assert "required_columns:orders" in failed


def test_cli_creates_sample_and_json_report(tmp_path, monkeypatch):
    database = tmp_path / "sample.sqlite"
    report = tmp_path / "reports" / "quality.json"
    monkeypatch.setattr(sys, "argv", [
        "db-quality", "--database", str(database), "--report", str(report), "--create-sample"
    ])
    assert main() == 0
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "PASS"


def test_cli_returns_nonzero_when_violations_exist(tmp_path, monkeypatch):
    database = tmp_path / "dirty.sqlite"
    create_sample_database(database)
    with sqlite3.connect(database) as con:
        con.execute("UPDATE orders SET amount = 0 WHERE order_id = 1001")
    monkeypatch.setattr(sys, "argv", ["db-quality", "--database", str(database), "--report", str(tmp_path / "bad.json")])
    assert main() == 1


def test_run_checks_uses_open_connection(tmp_path):
    database = tmp_path / "sample.sqlite"
    create_sample_database(database)
    with sqlite3.connect(database) as con:
        results = run_checks(con)
    assert all(item["status"] == "PASS" for item in results)
