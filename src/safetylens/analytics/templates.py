"""Run the parameterized SQL templates and return typed rows.

Why pydantic rows: these results cross into the answer engine and the validator, which must know
exactly which numbers came from SQL (CLAUDE.md rule 1). No SQL is built here; every query is a
named .sql file with bound parameters (rule 5).
"""

import datetime as dt
import re
from typing import Any

import duckdb
from pydantic import BaseModel

from safetylens.store.sql import load_sql

_KEY_STRIP = re.compile(r"[\s-]")


def model_key(model: str) -> str:
    """Canonical model key; must match the regexp_replace in build_complaints.sql."""
    return _KEY_STRIP.sub("", model.upper())


class VehicleFilter(BaseModel):
    make: str
    model: str
    year_from: int | None = None
    year_to: int | None = None
    received_from: dt.date | None = None
    received_to: dt.date | None = None
    component_system: str | None = None

    def params(self) -> dict[str, Any]:
        return {
            "make": self.make.strip().upper(),
            "model_key": model_key(self.model),
            "year_from": self.year_from,
            "year_to": self.year_to,
            "received_from": self.received_from,
            "received_to": self.received_to,
            "component_system": self.component_system,
        }


class ComponentCount(BaseModel):
    component_system: str | None
    component: str | None
    complaints: int
    crashes: int
    fires: int


class MonthCount(BaseModel):
    month: dt.date
    complaints: int


class Severity(BaseModel):
    complaints: int
    with_crash: int
    with_fire: int
    with_injury: int
    with_death: int
    injured: int
    deaths: int


class RecallCampaign(BaseModel):
    campno: str
    report_date: dt.date | None
    components: list[str]
    manufacturer: str | None
    potentially_affected: int | None
    consequence: str | None
    remedy: str | None
    do_not_drive: bool
    park_outside: bool
    campaigns_total: int


def _rows(
    con: duckdb.DuckDBPyConnection, name: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    cur = con.execute(load_sql(name), params)
    columns = [d[0] for d in cur.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


def complaint_count(con: duckdb.DuckDBPyConnection, f: VehicleFilter) -> int:
    return int(_rows(con, "complaint_count", f.params())[0]["complaints"])


def top_components(
    con: duckdb.DuckDBPyConnection, f: VehicleFilter, limit: int = 10
) -> list[ComponentCount]:
    rows = _rows(con, "top_components", {**f.params(), "limit": limit})
    return [ComponentCount.model_validate(r) for r in rows]


def monthly_trend(con: duckdb.DuckDBPyConnection, f: VehicleFilter) -> list[MonthCount]:
    return [MonthCount.model_validate(r) for r in _rows(con, "monthly_trend", f.params())]


def severity(con: duckdb.DuckDBPyConnection, f: VehicleFilter) -> Severity:
    return Severity.model_validate(_rows(con, "severity", f.params())[0])


def recalls_by_vehicle(con: duckdb.DuckDBPyConnection, f: VehicleFilter) -> list[RecallCampaign]:
    params = f.params()
    for unused in ("received_from", "received_to"):
        params.pop(unused)
    return [RecallCampaign.model_validate(r) for r in _rows(con, "recalls_by_vehicle", params)]
