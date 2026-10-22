"""Data-quality checks on the raw and normalized tables (gate D3).

Why exit non-zero on any failure: a data problem found here is cheap; found later it would show up
as a wrong count in an answer.
"""

from dataclasses import dataclass

import duckdb

from safetylens.store import db
from safetylens.store.build import BUILT_TABLES
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
REQUIRED_TABLES = ("complaints_raw", "recalls_raw", "ingest_runs", *BUILT_TABLES)


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


def _zero(name: str, value: int, what: str) -> CheckResult:
    return CheckResult(name, value == 0, f"{value} {what}")


def run_checks(con: duckdb.DuckDBPyConnection) -> list[CheckResult]:
    rows = con.execute(load_sql("dq_tables_present"), [list(REQUIRED_TABLES)]).fetchall()
    present = {r[0] for r in rows}
    missing = [t for t in REQUIRED_TABLES if t not in present]
    if missing:
        hint = "run `make data-dev` (ingest + build)"
        return [CheckResult("tables present", False, f"missing {missing}; {hint}")]

    complaints = db.summarize(con, "complaints")
    recalls = db.summarize(con, "recalls")
    pii_rows = con.execute(load_sql("dq_pii_columns"), [list(FORBIDDEN_COLUMNS)]).fetchall()
    pii = [r[0] for r in pii_rows]
    product_repeats = _scalar(con, "dq_product_repeats")
    return [
        CheckResult("complaints loaded", complaints.row_count > 0, f"{complaints.row_count} rows"),
        CheckResult(
            "distinct complaints",
            complaints.distinct_keys > 0,
            f"{complaints.distinct_keys} distinct ODINO",
        ),
        _zero("0 missing ODINO", _scalar(con, "dq_missing_odino"), "missing"),
        _zero(
            "0 duplicate vehicle (odino, component)",
            _scalar(con, "dq_duplicate_components"),
            "duplicated pairs among prod_type='V'",
        ),
        CheckResult(
            "repeated non-vehicle product rows",
            True,
            f"{product_repeats} groups (tires, equipment, child seats; not a gate)",
            gate=False,
        ),
        CheckResult("recalls loaded", recalls.row_count > 0, f"{recalls.row_count} rows"),
        _zero("0 missing CAMPNO", _scalar(con, "dq_missing_campno"), "missing"),
        _zero(
            "complaints: one row per (odino, component)",
            _scalar(con, "dq_complaints_unique"),
            "duplicated pairs",
        ),
        _zero("complaint_docs: one row per complaint", _scalar(con, "dq_docs_match"), "rows off"),
        _zero(
            "complaint fields agree across components",
            _scalar(con, "dq_complaint_attrs_consistent"),
            "complaints with conflicting fields",
        ),
        _zero(
            "recalls: one row per (campaign, vehicle, component)",
            _scalar(con, "dq_recalls_unique"),
            "duplicated rows",
        ),
        CheckResult("PII columns absent", not pii, "none found" if not pii else ", ".join(pii)),
    ]


def _label(result: CheckResult) -> str:
    if not result.gate:
        return "INFO"
    return "PASS" if result.passed else "FAIL"


def format_report(results: list[CheckResult]) -> str:
    return "\n".join(f"[{_label(r)}] {r.name}: {r.detail}" for r in results)
