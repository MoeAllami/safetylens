"""Answer cache: the same question about the same data gets the same verified answer, fast.

Why the key is the normalized plan, not the question text: "F150 brake problems" and "brake
complaints on the Ford F-150" resolve to the same intent, vehicle and filters, so they share an
answer. The key also holds a data version and an answer version, so new data, a new prompt or a
new writer model can never serve a stale answer. Only verified answers are stored.
"""

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

import duckdb

from safetylens.answer import prompts
from safetylens.answer.compute import parse_date
from safetylens.answer.models import Answer, QueryPlan, ResolvedVehicle
from safetylens.store.sql import load_sql

CACHEABLE = ("answered", "fallback_template")


def data_version(con: duckdb.DuckDBPyConnection) -> str:
    row = con.execute(load_sql("data_version")).fetchone()
    return json.dumps(list(row or []), default=str)


def cache_key(
    plan: QueryPlan, vehicles: list[ResolvedVehicle], data: str, answer_version: str
) -> str:
    normalized = {
        "intent": plan.intent,
        "vehicles": [[v.make, v.model_key, v.year_from, v.year_to] for v in vehicles],
        "component_system": plan.component_system,
        "received": [str(parse_date(plan.received_from)), str(parse_date(plan.received_to))],
        "search_text": " ".join(plan.search_text.lower().split()),
        "data": data,
        "answer_version": answer_version,
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def answer_version(writer: str) -> str:
    """Changes whenever the prompts or the writer configuration (model, effort) change."""
    text = "\n".join([prompts.PLANNER, prompts.WRITER, prompts.RETRY, writer])
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class AnswerCache:
    def __init__(self, path: Path, writer: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # One connection shared by request threads, so every use goes through the lock.
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(load_sql("cache_create"))
        self._lock = threading.Lock()
        self.version = answer_version(writer)

    def get(self, key: str) -> Answer | None:
        with self._lock:
            row = self._db.execute(load_sql("cache_get"), (key,)).fetchone()
        return Answer.model_validate_json(row[0]) if row else None

    def put(self, key: str, answer: Answer) -> None:
        if answer.status not in CACHEABLE:
            return
        with self._lock, self._db:
            self._db.execute(load_sql("cache_put"), (key, answer.model_dump_json()))

    def clear(self) -> int:
        with self._lock, self._db:
            return self._db.execute(load_sql("cache_clear")).rowcount

    def close(self) -> None:
        with self._lock:
            self._db.close()
