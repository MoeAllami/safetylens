"""Record pages: one complaint, one recall campaign, one vehicle's summary.

Why record pages: every citation in an answer links here, so a reader can check the claim
against the record itself and follow it to NHTSA. Each page reads through its own cursor,
because a DuckDB connection must not be shared across request threads.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from safetylens.analytics import templates as t
from safetylens.answer.models import VehicleRef
from safetylens.answer.resolver import resolve
from safetylens.web import records
from safetylens.web.charts import components_chart, trend_chart
from safetylens.web.state import templates

router = APIRouter()
VEHICLE_TOP_N = 10


def _not_found(request: Request, message: str, options: list[str] | None = None) -> HTMLResponse:
    return templates(request).TemplateResponse(
        request, "not_found.html", {"message": message, "options": options or []}, status_code=404
    )


@router.get("/complaint/{odino}", response_class=HTMLResponse)
def complaint(request: Request, odino: str) -> HTMLResponse:
    record = records.complaint(request.app.state.con.cursor(), odino)
    if record is None:
        return _not_found(request, "No complaint with that ODI number.")
    return templates(request).TemplateResponse(request, "complaint.html", {"c": record})


@router.get("/recall/{campno}", response_class=HTMLResponse)
def recall(request: Request, campno: str) -> HTMLResponse:
    record = records.recall(request.app.state.con.cursor(), campno)
    if record is None:
        return _not_found(request, "No recall campaign with that number.")
    return templates(request).TemplateResponse(request, "recall.html", {"r": record})


@router.get("/vehicle/{make}/{model}/{year}", response_class=HTMLResponse)
def vehicle(request: Request, make: str, model: str, year: int) -> HTMLResponse:
    con = request.app.state.con.cursor()
    res = resolve(con, VehicleRef(make=make, model=model, year_from=year, year_to=year))
    if res.status != "ok" or res.vehicle is None:
        return _not_found(request, "Which vehicle did you mean?", res.options)
    v = res.vehicle
    f = t.VehicleFilter(make=v.make, model=v.model_key, year_from=year, year_to=year)
    top = [c.model_dump() for c in t.top_components(con, f, limit=VEHICLE_TOP_N)]
    trend = [m.model_dump() for m in t.monthly_trend(con, f)]
    context = {
        "v": v,
        "count": t.complaint_count(con, f),
        "severity": t.severity(con, f),
        "top": top,
        "recalls": t.recalls_by_vehicle(con, f),
        "charts": [c for c in (components_chart(top), trend_chart(trend)) if c is not None],
    }
    return templates(request).TemplateResponse(request, "vehicle.html", context)
