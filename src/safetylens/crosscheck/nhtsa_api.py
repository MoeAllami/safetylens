"""A small, polite client for the NHTSA public API, used only for cross-checks.

Why keep only ODI numbers: API complaint results include the VIN and the narrative. Those must
never be stored or logged (CLAUDE.md rule 4), so responses are reduced to the ODI number and the
vehicle products before anything is cached, and the raw JSON is dropped immediately.
"""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

API_BASE = "https://api.nhtsa.gov"


class VehicleProduct(BaseModel):
    model: str
    year: int | None


class ComplaintRef(BaseModel):
    odi: str
    vehicles: list[VehicleProduct]


class RetryableError(Exception):
    """Server error or dropped connection worth one more try."""


def _year(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


class NhtsaApi:
    def __init__(
        self,
        client: httpx.Client,
        cache_dir: Path,
        *,
        min_interval: float = 1.0,
        attempts: int = 3,
        max_cache_age_s: float = 24 * 3600,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._cache_dir = cache_dir
        self._min_interval = min_interval
        self._attempts = attempts
        self._max_cache_age_s = max_cache_age_s
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    def _get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        for attempt in range(1, self._attempts + 1):
            if self._last_request is not None:
                wait = self._last_request + self._min_interval - self._clock()
                if wait > 0:
                    self._sleep(wait)
            try:
                resp = self._client.get(API_BASE + path, params=params)
                self._last_request = self._clock()
                if resp.status_code >= 500:
                    raise RetryableError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data
            except (httpx.TransportError, RetryableError):
                self._last_request = self._clock()
                if attempt == self._attempts:
                    raise
                self._sleep(2.0**attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def _cache_path(self, kind: str, params: dict[str, str | int]) -> Path:
        key = json.dumps([kind, sorted(params.items())], default=str)
        return self._cache_dir / f"{kind}-{hashlib.sha256(key.encode()).hexdigest()[:16]}.json"

    def _cached(self, kind: str, params: dict[str, str | int], fetch: Callable[[], Any]) -> Any:
        path = self._cache_path(kind, params)
        if path.exists() and time.time() - path.stat().st_mtime < self._max_cache_age_s:
            return json.loads(path.read_text(encoding="utf-8"))["value"]
        value = fetch()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        tmp.write_text(json.dumps({"query": params, "value": value}), encoding="utf-8")
        tmp.replace(path)
        return value

    def model_names(self, make: str, year: int) -> list[str]:
        """The API's own model names for a make and year, e.g. 'MODEL Y (All Variants)'."""
        params: dict[str, str | int] = {"modelYear": year, "make": make, "issueType": "c"}

        def fetch() -> list[str]:
            data = self._get("/products/vehicle/models", params)
            return sorted({str(r["model"]) for r in data.get("results", []) if r.get("model")})

        names: list[str] = self._cached("models", params, fetch)
        return names

    def complaints(self, make: str, model: str, year: int) -> list[ComplaintRef]:
        """Complaints the API returns for one of its model names, reduced to ODI + vehicles."""
        params: dict[str, str | int] = {"make": make, "model": model, "modelYear": year}

        def fetch() -> list[dict[str, Any]]:
            data = self._get("/complaints/complaintsByVehicle", params)
            refs = [
                ComplaintRef(
                    odi=str(r["odiNumber"]),
                    vehicles=[
                        VehicleProduct(
                            model=str(p.get("productModel", "")), year=_year(p.get("productYear"))
                        )
                        for p in r.get("products", [])
                        if p.get("type") == "Vehicle"
                    ],
                )
                for r in data.get("results", [])
            ]
            return [ref.model_dump() for ref in refs]

        return [ComplaintRef.model_validate(r) for r in self._cached("complaints", params, fetch)]
