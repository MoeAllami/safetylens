"""Check the templates against an independent plain-Python count over the committed real sample.

Why an oracle: the golden tests prove the rules on tiny hand-made data; this proves the SQL agrees
with a second, much simpler implementation on real NHTSA rows.
"""

from collections import defaultdict
from pathlib import Path

import duckdb
import pytest
from builders import make_db

from safetylens.analytics import templates as t

FIXTURES = Path(__file__).parents[1] / "fixtures"
Vehicle = tuple[str, str, int]


def _vehicle_rows() -> list[list[str]]:
    text = (FIXTURES / "complaints_sample.txt").read_bytes().decode("utf-8")
    rows = [line.split("\t") for line in text.split("\r\n") if line]
    return [f for f in rows if f[45] == "V"]


def _oracle() -> tuple[
    dict[Vehicle, set[str]], dict[tuple[Vehicle, str], set[str]], dict[Vehicle, dict[str, int]]
]:
    complaints: dict[Vehicle, set[str]] = defaultdict(set)
    by_component: dict[tuple[Vehicle, str], set[str]] = defaultdict(set)
    injured: dict[Vehicle, dict[str, int]] = defaultdict(dict)
    for f in _vehicle_rows():
        if f[5] == "9999":
            continue
        vehicle = (f[3].strip().upper(), t.model_key(f[4].strip()), int(f[5]))
        complaints[vehicle].add(f[1])
        by_component[(vehicle, f[11])].add(f[1])
        injured[vehicle][f[1]] = int(f[9] or 0)  # per complaint, so repeats overwrite, never add
    return complaints, by_component, injured


@pytest.fixture(scope="module")
def con(tmp_path_factory: pytest.TempPathFactory) -> duckdb.DuckDBPyConnection:
    text = (FIXTURES / "complaints_sample.txt").read_bytes().decode("utf-8")
    recalls = (FIXTURES / "recalls_sample.txt").read_bytes().decode("utf-8")
    return make_db(
        tmp_path_factory.mktemp("oracle"),
        [line for line in text.split("\r\n") if line],
        [line for line in recalls.split("\r\n") if line],
    )


def _top_vehicles(n: int) -> list[Vehicle]:
    complaints, _, _ = _oracle()
    return sorted(complaints, key=lambda v: (-len(complaints[v]), v))[:n]


def _filter(v: Vehicle) -> t.VehicleFilter:
    # model_key is idempotent, so the oracle's key can be passed as the model name.
    return t.VehicleFilter(make=v[0], model=v[1], year_from=v[2], year_to=v[2])


def test_complaint_counts_match_oracle(con: duckdb.DuckDBPyConnection) -> None:
    complaints, _, _ = _oracle()
    for v in _top_vehicles(10):
        assert t.complaint_count(con, _filter(v)) == len(complaints[v]), v


def test_component_counts_match_oracle(con: duckdb.DuckDBPyConnection) -> None:
    _, by_component, _ = _oracle()
    for v in _top_vehicles(3):
        got = {x.component: x.complaints for x in t.top_components(con, _filter(v), limit=1000)}
        want = {comp: len(odis) for (veh, comp), odis in by_component.items() if veh == v}
        assert got == want, v


def test_injuries_match_oracle(con: duckdb.DuckDBPyConnection) -> None:
    _, _, injured = _oracle()
    for v in _top_vehicles(10):
        assert t.severity(con, _filter(v)).injured == sum(injured[v].values()), v
