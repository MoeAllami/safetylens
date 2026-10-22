from pathlib import Path

import httpx
import respx
from builders import complaint_line, make_db, recall_line

from safetylens.crosscheck.crosscheck import (
    CrosscheckVehicle,
    api_distinct_odis,
    crosscheck,
    format_table,
    load_vehicles,
)
from safetylens.crosscheck.nhtsa_api import API_BASE, NhtsaApi

MODELS = f"{API_BASE}/products/vehicle/models"
COMPLAINTS = f"{API_BASE}/complaints/complaintsByVehicle"
FAKE_VIN = "1FTFW1E5XNFA00000"
FAKE_NARRATIVE = "MY NAME IS JANE AND MY BRAKES FAILED"


def _complaint(odi: int, model: str, year: str = "2022") -> dict[str, object]:
    return {
        "odiNumber": odi,
        "vin": FAKE_VIN,
        "summary": FAKE_NARRATIVE,
        "products": [
            {"type": "Vehicle", "productModel": model, "productYear": year},
            {"type": "Tire", "productModel": "G-METRIC", "productYear": "9999"},
        ],
    }


def _mock_ford(router: respx.MockRouter) -> None:
    router.get(MODELS, params={"make": "FORD", "modelYear": "2022"}).respond(
        json={
            "results": [
                {"model": "F-150 SUPER CREW"},
                {"model": "F-150 SUPER CREW"},
                {"model": "F-150 SUPER CREW HEV"},
                {"model": "F-250 CREW CAB"},
            ]
        }
    )
    router.get(COMPLAINTS, params={"model": "F-150 SUPER CREW"}).respond(
        json={
            "results": [
                _complaint(1, "F-150"),
                _complaint(2, "F-150"),
                _complaint(3, "F-150 HYBRID"),
                _complaint(9, "F-150", year="2021"),
            ]
        }
    )
    router.get(COMPLAINTS, params={"model": "F-150 SUPER CREW HEV"}).respond(
        json={
            "results": [
                _complaint(2, "F-150"),
                _complaint(3, "F-150 HYBRID"),
            ]
        }
    )


def _api(tmp_path: Path, client: httpx.Client, sleeps: list[float] | None = None) -> NhtsaApi:
    log = sleeps if sleeps is not None else []
    return NhtsaApi(client, tmp_path / "cache", sleep=log.append, clock=lambda: 0.0)


F150 = CrosscheckVehicle(make="FORD", model="F-150", year=2022)


def test_counts_distinct_odis_across_api_names(tmp_path: Path) -> None:
    with respx.mock(assert_all_called=False) as router, httpx.Client() as client:
        _mock_ford(router)
        f250 = router.get(COMPLAINTS, params={"model": "F-250 CREW CAB"}).respond(
            json={"results": []}
        )
        odis, used = api_distinct_odis(_api(tmp_path, client), F150)
    assert odis == {"1", "2"}  # 3 is a hybrid, 9 is model year 2021, 2 is counted once
    assert used == ["F-150 SUPER CREW", "F-150 SUPER CREW HEV"]
    assert not f250.called  # names that do not start with our model are never asked


def test_vin_and_narrative_are_never_cached(tmp_path: Path) -> None:
    with respx.mock(assert_all_called=False) as router, httpx.Client() as client:
        _mock_ford(router)
        api_distinct_odis(_api(tmp_path, client), F150)
    cached = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "cache").glob("*.json"))
    assert cached
    assert FAKE_VIN not in cached
    assert FAKE_NARRATIVE not in cached


def test_second_run_uses_cache(tmp_path: Path) -> None:
    with respx.mock(assert_all_called=False) as router, httpx.Client() as client:
        _mock_ford(router)
        api_distinct_odis(_api(tmp_path, client), F150)
        calls = len(router.calls)
        odis, _ = api_distinct_odis(_api(tmp_path, client), F150)
        assert len(router.calls) == calls
    assert odis == {"1", "2"}


def test_waits_between_requests(tmp_path: Path) -> None:
    sleeps: list[float] = []
    with respx.mock(assert_all_called=False) as router, httpx.Client() as client:
        _mock_ford(router)
        api_distinct_odis(_api(tmp_path, client, sleeps), F150)
    assert sleeps == [1.0, 1.0]  # 3 requests, at most 1 per second


def test_retries_server_errors(tmp_path: Path) -> None:
    sleeps: list[float] = []
    with respx.mock as router, httpx.Client() as client:
        router.get(MODELS).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json={"results": []})]
        )
        api = NhtsaApi(client, tmp_path / "cache", min_interval=0.0, sleep=sleeps.append)
        assert api.model_names("FORD", 2022) == []
    assert sleeps == [2.0]


def test_crosscheck_passes_and_fails(tmp_path: Path) -> None:
    con = make_db(
        tmp_path,
        [complaint_line("1"), complaint_line("1", compdesc="STEERING"), complaint_line("2")],
        [recall_line()],
    )
    model_y = CrosscheckVehicle(make="TESLA", model="MODEL Y", year=2024)
    with respx.mock(assert_all_called=False) as router, httpx.Client() as client:
        _mock_ford(router)
        router.get(MODELS, params={"make": "TESLA"}).respond(json={"results": []})
        router.get(COMPLAINTS, params={"model": "MODEL Y"}).respond(json={"results": []})
        results = crosscheck(con, _api(tmp_path, client), [F150, model_y])
    assert [(r.ours, r.theirs, r.passed) for r in results] == [(2, 2, True), (0, 0, False)]
    assert results[1].diff_pct is None
    assert format_table(results).endswith("1/2 within 2%")


def test_load_vehicles(tmp_path: Path) -> None:
    path = tmp_path / "v.yaml"
    path.write_text("vehicles:\n  - {make: FORD, model: F-150, year: 2022}\n", encoding="utf-8")
    assert load_vehicles(path) == [F150]
