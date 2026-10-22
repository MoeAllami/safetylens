"""Look up one complaint or one recall campaign for its record page.

Why the id patterns: a path segment is user input, so it is checked against the shape of a real
ODI or campaign number before it reaches SQL (the query is parameterized anyway). Only columns
kept at ingest exist in the tables, so nothing here can show a VIN, city, dealer or operator.
"""

import datetime as dt
import re
from typing import Any

import duckdb
from pydantic import BaseModel

from safetylens.store.sql import load_sql

ODI = re.compile(r"[0-9]{6,9}")
CAMPAIGN = re.compile(r"[0-9]{2}[A-Z][0-9]{6}")


def complaint_url(odino: str) -> str:
    return f"https://api.nhtsa.gov/complaints/odinumber?odinumber={odino}"


def recall_url(campno: str) -> str:
    return f"https://www.nhtsa.gov/recalls?nhtsaId={campno}"


class ComplaintRecord(BaseModel):
    odino: str
    make: str | None
    model: str | None
    model_year: int | None
    received_date: dt.date | None
    fail_date: dt.date | None
    crash: bool | None
    fire: bool | None
    injured: int | None
    deaths: int | None
    miles: int | None
    veh_speed: int | None
    state: str | None
    components: list[str]
    narrative: str | None


class RecallVehicle(BaseModel):
    make: str | None
    model: str | None
    model_year: int | None
    components: list[str]


class RecallRecord(BaseModel):
    campno: str
    manufacturer: str | None
    report_date: dt.date | None
    owner_notice_date: dt.date | None
    potentially_affected: int | None
    defect_summary: str | None
    consequence: str | None
    remedy: str | None
    do_not_drive: bool
    park_outside: bool
    vehicles: list[RecallVehicle] = []


def _rows(
    con: duckdb.DuckDBPyConnection, name: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    cur = con.execute(load_sql(name), params)
    columns = [d[0] for d in cur.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


def complaint(con: duckdb.DuckDBPyConnection, odino: str) -> ComplaintRecord | None:
    if not ODI.fullmatch(odino):
        return None
    rows = _rows(con, "complaint_record", {"odino": odino})
    return ComplaintRecord.model_validate(rows[0]) if rows else None


def recall(con: duckdb.DuckDBPyConnection, campno: str) -> RecallRecord | None:
    campno = campno.upper()
    if not CAMPAIGN.fullmatch(campno):
        return None
    rows = _rows(con, "recall_record", {"campno": campno})
    if not rows:
        return None
    vehicles = [
        RecallVehicle.model_validate(r) for r in _rows(con, "recall_vehicles", {"campno": campno})
    ]
    return RecallRecord.model_validate({**rows[0], "vehicles": vehicles})
