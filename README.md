# Database Quality Validator

A lightweight database QA framework that profiles a SQLite database, executes reusable SQL quality rules and exports a machine-readable validation report.

## Checks included

- Required tables and columns exist.
- Customer IDs and emails are populated.
- Customer email business keys are unique.
- Order IDs are unique and required fields are populated.
- Orders reference existing customers.
- Order amounts are positive and finite.
- Order dates are valid ISO dates.
- Order statuses belong to an allowed set.

Each check returns a failure count and pass/fail status. The CLI exits with code 1 when data-quality violations are found, making it suitable for CI and scheduled data checks.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m db_quality_validator --create-sample --database output/sample.sqlite --report output/quality_report.json
pytest
```

Validate an existing SQLite database:

```bash
python -m db_quality_validator --database path/to/database.sqlite --report quality_report.json
```

Exit codes: `0` = all checks passed; `1` = validation executed but issues were found; `2` = input or execution error.

## Sample data

The sample database is deliberately clean and deterministic. Tests introduce controlled defects (duplicates, orphan rows, invalid amounts and dates) to verify that the checks detect them.

## Architecture

- `sql/schema.sql`: sample database schema.
- `sql/seed.sql`: clean demonstration data.
- `src/db_quality_validator/validator.py`: schema inspection, SQL checks, reporting and CLI.
- `tests/`: positive, negative and CLI tests.

## Limitations

This version targets SQLite. Rules are explicit and auditable; they are not a substitute for source-system constraints or a full data observability platform. No database credentials, server or Docker are required.

## License

MIT. See [LICENSE](LICENSE).
