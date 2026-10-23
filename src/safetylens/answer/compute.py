"""Run the SQL templates an intent needs. Every number an answer may use comes from here.

Why per-intent recipes: the planner only chooses the intent and filters; which queries run is
fixed code (CLAUDE.md rule 5), so the model can never invent a calculation.
"""

import datetime as dt
from typing import Any

import duckdb

from safetylens.analytics import templates as t
from safetylens.answer.models import ComputeResult, QueryPlan, ResolvedVehicle
from safetylens.answer.numbers import numbers_from_values
from safetylens.store.sql import load_sql

TOP_N = 10
RECALL_TEXT_CHARS = 300


def known_systems(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [str(r[0]) for r in con.execute(load_sql("known_systems")).fetchall()]


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def vehicle_filter(v: ResolvedVehicle, plan: QueryPlan, system: str | None) -> t.VehicleFilter:
    return t.VehicleFilter(
        make=v.make,
        model=v.model_key,
        year_from=v.year_from,
        year_to=v.year_to,
        received_from=parse_date(plan.received_from),
        received_to=parse_date(plan.received_to),
        component_system=system,
    )


def _rows(models: list[Any], vehicle: str) -> list[dict[str, Any]]:
    return [{"vehicle": vehicle, **m.model_dump(mode="json")} for m in models]


def _recall_rows(campaigns: list[t.RecallCampaign], vehicle: str) -> list[dict[str, Any]]:
    rows = []
    for c in campaigns:
        row = c.model_dump(mode="json")
        for key in ("consequence", "remedy"):
            row[key] = (row[key] or "")[:RECALL_TEXT_CHARS]
        rows.append({"vehicle": vehicle, **row})
    return rows


def compute(
    con: duckdb.DuckDBPyConnection, plan: QueryPlan, vehicles: list[ResolvedVehicle]
) -> ComputeResult:
    system = plan.component_system if plan.component_system in known_systems(con) else None
    tables: dict[str, list[dict[str, Any]]] = {}

    def add(name: str, rows: list[dict[str, Any]]) -> None:
        tables.setdefault(name, []).extend(rows)

    for v in vehicles:
        f = vehicle_filter(v, plan, system)
        add("complaint_count", [{"vehicle": v.label, "complaints": t.complaint_count(con, f)}])
        if plan.intent in ("top_components", "compare"):
            limit = TOP_N if plan.intent == "top_components" else 5
            add("top_components", _rows(t.top_components(con, f, limit=limit), v.label))
            add("severity", _rows([t.severity(con, f)], v.label))
        elif plan.intent == "trend":
            add("monthly_trend", _rows(t.monthly_trend(con, f), v.label))
        elif plan.intent == "recalls":
            add("recalls", _recall_rows(t.recalls_by_vehicle(con, f), v.label))
    if system:
        add("filters", [{"component_system": system}])
    return ComputeResult(intent=plan.intent, vehicles=vehicles, tables=tables)


def allowed_numbers(result: ComputeResult, plan: QueryPlan) -> set[str]:
    """Numbers the prose may contain: anything in the SQL rows, vehicle labels and plan dates."""
    values: list[Any] = [result.tables]
    values += [v.label for v in result.vehicles]
    # Only dates that parsed and reached SQL; a malformed planner date vouches for nothing.
    values += [
        d.isoformat() for d in (parse_date(plan.received_from), parse_date(plan.received_to)) if d
    ]
    return numbers_from_values(values)
