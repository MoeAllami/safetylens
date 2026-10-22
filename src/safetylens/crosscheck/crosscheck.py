"""Cross-check our distinct-complaint counts against the live NHTSA API (gate D4).

Why try several API model names: the API only answers to its own names ('F-150 SUPER CREW',
'MODEL Y (All Variants)'), while results carry the flat-file name ('F-150'). So we ask under every
API name that starts with our model, keep complaints whose vehicle is exactly our model and year,
and count distinct ODI numbers across all of them.
"""

from pathlib import Path

import duckdb
import yaml
from pydantic import BaseModel

from safetylens.analytics.templates import VehicleFilter, complaint_count, model_key
from safetylens.crosscheck.nhtsa_api import NhtsaApi

TOLERANCE_PCT = 2.0


class CrosscheckVehicle(BaseModel):
    make: str
    model: str
    year: int


class CrosscheckResult(BaseModel):
    vehicle: CrosscheckVehicle
    ours: int
    theirs: int
    api_models: list[str]
    diff_pct: float | None
    passed: bool


def load_vehicles(path: Path) -> list[CrosscheckVehicle]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [CrosscheckVehicle.model_validate(v) for v in data["vehicles"]]


def api_distinct_odis(api: NhtsaApi, v: CrosscheckVehicle) -> tuple[set[str], list[str]]:
    key = model_key(v.model)
    names = [n for n in api.model_names(v.make, v.year) if model_key(n).startswith(key)]
    odis: set[str] = set()
    used: list[str] = []
    for name in names or [v.model]:
        hits = {
            ref.odi
            for ref in api.complaints(v.make, name, v.year)
            if any(model_key(p.model) == key and p.year == v.year for p in ref.vehicles)
        }
        if hits:
            used.append(name)
            odis |= hits
    return odis, used


def crosscheck(
    con: duckdb.DuckDBPyConnection, api: NhtsaApi, vehicles: list[CrosscheckVehicle]
) -> list[CrosscheckResult]:
    results = []
    for v in vehicles:
        f = VehicleFilter(make=v.make, model=v.model, year_from=v.year, year_to=v.year)
        ours = complaint_count(con, f)
        odis, used = api_distinct_odis(api, v)
        theirs = len(odis)
        diff = abs(ours - theirs) / theirs * 100 if theirs else None
        passed = diff is not None and diff <= TOLERANCE_PCT
        results.append(
            CrosscheckResult(
                vehicle=v, ours=ours, theirs=theirs, api_models=used, diff_pct=diff, passed=passed
            )
        )
    return results


def format_table(results: list[CrosscheckResult]) -> str:
    lines = [f"{'vehicle':<34} {'ours':>6} {'nhtsa':>6} {'diff':>7}  result"]
    for r in results:
        v = r.vehicle
        diff = "n/a" if r.diff_pct is None else f"{r.diff_pct:.2f}%"
        name = f"{v.year} {v.make} {v.model}"
        lines.append(
            f"{name:<34} {r.ours:>6} {r.theirs:>6} {diff:>7}  {'PASS' if r.passed else 'FAIL'}"
        )
    passed = sum(r.passed for r in results)
    lines.append(f"{passed}/{len(results)} within {TOLERANCE_PCT:.0f}%")
    return "\n".join(lines)
