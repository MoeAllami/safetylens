"""Data-quality checks on the raw tables (gate D3).

Why exit non-zero on any failure: a data problem found here is cheap; found later it would show up
as a wrong count in an answer.
"""

from dataclasses import dataclass

import duckdb

from safetylens.store import db
from safetylens.store.sql import load_sql

# Personal data that must never reach DuckDB (CLAUDE.md rule 4).
FORBIDDEN_COLUMNS = (
    "city",
    "vin",
    "vehicle_operator",
    "dealer_name",
    "dealer_tel",
    "dealer_city",
    "dealer_state",
    "dealer_zip",
)
REQUIRED_TABLES = ("complaints_raw", "recalls_raw", "ingest_runs")


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str
    gate: bool = True  # False = reported for awareness only, never fails the run


def _scalar(con: duckdb.DuckDBPyConnection, query: str) -> int:
    row = con.execute(load_sql(query)).fetchone()
    if row is None:
        raise RuntimeError(f"{query} returned no row")
    return int(row[0])


def run_checks(con: duckdb.DuckDBPyConnection) -> list[CheckResult]:
    present = {r[0] for r in con.execute(load_sql("dq_tables_present")).fetchall()}
    missing = [t for t in REQUIRED_TABLES if t not in present]
    if missing:
        return [CheckResult("tables present", False, f"missing {missing}; run `make data-dev`")]

    complaints = db.summarize(con, "complaints")
    recalls = db.summarize(con, "recalls")
    pii = [
        r[0] for r in con.execute(load_sql("dq_pii_columns"), [list(FORBIDDEN_COLUMNS)]).fetchall()
    ]
    missing_odino = _scalar(con, "dq_missing_odino")
    duplicates = _scalar(con, "dq_duplicate_components")
    missing_campno = _scalar(con, "dq_missing_campno")
    product_repeats = _scalar(con, "dq_product_repeats")
    return [
        CheckResult("complaints loaded", complaints.row_count > 0, f"{complaints.row_count} rows"),
        CheckResult(
            "distinct complaints",
            complaints.distinct_keys > 0,
            f"{complaints.distinct_keys} distinct ODINO",
        ),
        CheckResult("0 missing ODINO", missing_odino == 0, f"{missing_odino} missing"),
        CheckResult(
            "0 duplicate vehicle (odino, component)",
            duplicates == 0,
            f"{duplicates} duplicated pairs among prod_type='V'",
        ),
        CheckResult(
            "repeated non-vehicle product rows",
            True,
            f"{product_repeats} groups (tires, equipment, child seats; not a gate)",
            gate=False,
        ),
        CheckResult("recalls loaded", recalls.row_count > 0, f"{recalls.row_count} rows"),
        CheckResult("0 missing CAMPNO", missing_campno == 0, f"{missing_campno} missing"),
        CheckResult("PII columns absent", not pii, "none found" if not pii else ", ".join(pii)),
    ]


def _label(result: CheckResult) -> str:
    if not result.gate:
        return "INFO"
    return "PASS" if result.passed else "FAIL"


def format_report(results: list[CheckResult]) -> str:
    return "\n".join(f"[{_label(r)}] {r.name}: {r.detail}" for r in results)
