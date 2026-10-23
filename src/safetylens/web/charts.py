"""Vega-Lite chart specs, built with Altair from SQL rows only.

Why Altair: it describes a chart as data (a JSON spec) instead of drawing pixels in Python, so
the page just hands the spec to vega-embed. The numbers in a chart are the SQL rows themselves,
never anything a model wrote.
"""

from typing import Any, cast

import altair as alt


def trend_chart(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Complaints per received month (rows have month and complaints, optionally vehicle)."""
    if not rows:
        return None
    data = [
        {
            "month": str(r["month"])[:10],
            "complaints": r["complaints"],
            "vehicle": r.get("vehicle", ""),
        }
        for r in rows
    ]
    chart = (
        alt.Chart(alt.InlineData(values=data))
        .mark_line(point=True)
        .encode(
            x=alt.X("month:T", title="Month received"),
            y=alt.Y("complaints:Q", title="Distinct complaints"),
            color=alt.Color("vehicle:N", title="Vehicle"),
            tooltip=["vehicle:N", alt.Tooltip("month:T", format="%Y-%m"), "complaints:Q"],
        )
        .properties(width="container", height=240)
    )
    return cast(dict[str, Any], chart.to_dict())


def components_chart(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Distinct complaints per component (rows: component, complaints, optionally vehicle)."""
    if not rows:
        return None
    data = [
        {
            "component": r["component"] or "UNKNOWN",
            "complaints": r["complaints"],
            "vehicle": r.get("vehicle", ""),
        }
        for r in rows
    ]
    chart = (
        alt.Chart(alt.InlineData(values=data))
        .mark_bar()
        .encode(
            x=alt.X("complaints:Q", title="Distinct complaints"),
            y=alt.Y("component:N", sort="-x", title=None),
            color=alt.Color("vehicle:N", title="Vehicle"),
            tooltip=["vehicle:N", "component:N", "complaints:Q"],
        )
        .properties(width="container", height=alt.Step(22))
    )
    return cast(dict[str, Any], chart.to_dict())


def charts_for(tables: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """The charts an answer's SQL results support, in display order."""
    specs = [
        components_chart(tables.get("top_components", [])),
        trend_chart(tables.get("monthly_trend", [])),
    ]
    return [s for s in specs if s is not None]
