"""Build the committed real-data samples in tests/fixtures from the downloaded dev slice.

Why a script: the fixture must be reproducible and reviewable, and personal-data fields must be
blanked by code, not by hand. Whole complaints are kept (every row of a sampled ODINO) so tests see
real multi-component and multi-product complaints. Selection uses a stable hash, so re-running on
the same downloads gives the same file.

Usage: uv run python scripts/make_fixtures.py   (after `make data-dev`)
"""

import hashlib
import zipfile
from collections import defaultdict
from pathlib import Path

RAW = Path("data/raw")
OUT = Path("tests/fixtures")
COMPLAINT_ZIPS = ("COMPLAINTS_RECEIVED_2020-2024.zip", "COMPLAINTS_RECEIVED_2025-2026.zip")
RECALL_ZIP = "FLAT_RCL_POST_2010.zip"
COMPLAINT_ROWS = 2000
RECALL_ROWS = 200
MULTI_PRODUCT_COMPLAINTS = 5  # complaints naming a vehicle and a tire/equipment/seat
# 1-based CITY 13, VIN 15, DEALER_* 41-45, VEHICLE_OPERATOR 51
PII_POSITIONS = (13, 15, 41, 42, 43, 44, 45, 51)


def _records(zip_path: Path) -> list[bytes]:
    with zipfile.ZipFile(zip_path) as zf:
        data = zf.read(zf.namelist()[0])
    return [line.rstrip(b"\r") for line in data.split(b"\n") if line.strip()]


def _blank_pii(record: bytes) -> bytes:
    fields = record.split(b"\t")
    for pos in PII_POSITIONS:
        if pos <= len(fields):
            fields[pos - 1] = b""
    return b"\t".join(fields)


def _stable_key(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()


def _sample(groups: dict[bytes, list[bytes]], target: int, first: list[bytes]) -> list[bytes]:
    chosen: list[bytes] = []
    order = first + sorted((k for k in groups if k not in first), key=_stable_key)
    for key in order:
        rows = groups[key]
        if len(chosen) + len(rows) <= target:
            chosen.extend(rows)
        if len(chosen) == target:
            break
    if len(chosen) != target:
        raise SystemExit(f"could not fill {target} rows exactly (got {len(chosen)})")
    return chosen


def _multi_product(groups: dict[bytes, list[bytes]]) -> list[bytes]:
    keys = []
    for key, rows in groups.items():
        types = {r.split(b"\t")[45] for r in rows}
        if b"V" in types and len(types) > 1:
            keys.append(key)
    return sorted(keys, key=_stable_key)[:MULTI_PRODUCT_COMPLAINTS]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    complaints: dict[bytes, list[bytes]] = defaultdict(list)
    for name in COMPLAINT_ZIPS:
        for record in _records(RAW / name):
            complaints[record.split(b"\t")[1]].append(_blank_pii(record))
    rows = _sample(complaints, COMPLAINT_ROWS, _multi_product(complaints))
    (OUT / "complaints_sample.txt").write_bytes(b"".join(r + b"\r\n" for r in rows))

    recalls: dict[bytes, list[bytes]] = defaultdict(list)
    for record in _records(RAW / RECALL_ZIP):
        recalls[record.split(b"\t")[1]].append(record)
    rows = _sample(recalls, RECALL_ROWS, [])
    (OUT / "recalls_sample.txt").write_bytes(b"".join(r + b"\r\n" for r in rows))
    print(f"wrote {COMPLAINT_ROWS} complaint rows and {RECALL_ROWS} recall rows to {OUT}")


if __name__ == "__main__":
    main()
