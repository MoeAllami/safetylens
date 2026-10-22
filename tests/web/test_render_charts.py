import json
from typing import Any

from safetylens.web.charts import charts_for, components_chart, trend_chart
from safetylens.web.render import answer_html


def values(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows a Vega-Lite spec plots (Altair stores inline data under a named dataset)."""
    data = spec["data"]
    return list(data["values"] if "values" in data else spec["datasets"][data["name"]])


def test_only_validated_citations_become_links() -> None:
    html = str(
        answer_html("Brakes [11000001] and [22V123000], not [11000009].", ["11000001", "22V123000"])
    )
    assert '<a href="/complaint/11000001" class="cite">' in html
    assert '<a href="/recall/22V123000" class="cite">' in html
    assert "[11000009]" in html and "/complaint/11000009" not in html


def test_paragraphs_bullets_and_bold() -> None:
    html = str(answer_html("Intro **bold**\n\n- first [11000001]\n- second", ["11000001"]))
    assert "<p>Intro <strong>bold</strong></p>" in html
    assert "<ul><li>first" in html and "<li>second</li></ul>" in html


def test_markup_from_the_model_is_escaped() -> None:
    html = str(answer_html('<script>alert("x")</script> **<i>x</i>**', []))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<strong>&lt;i&gt;x&lt;/i&gt;</strong>" in html


def test_charts_carry_exactly_the_sql_rows() -> None:
    rows = [{"vehicle": "2022 FORD F-150", "month": "2024-01-01", "complaints": 4}]
    spec = trend_chart(rows)
    assert spec is not None
    assert values(spec) == [{"month": "2024-01-01", "complaints": 4, "vehicle": "2022 FORD F-150"}]
    assert trend_chart([]) is None and components_chart([]) is None
    top = [{"vehicle": "v", "component": None, "complaints": 2}]
    bar = components_chart(top)
    assert bar is not None and values(bar)[0]["component"] == "UNKNOWN"
    assert json.dumps(bar)  # serializable for the data-spec attribute


def test_charts_for_picks_tables_in_order() -> None:
    tables = {
        "monthly_trend": [{"vehicle": "v", "month": "2024-01-01", "complaints": 1}],
        "top_components": [{"vehicle": "v", "component": "BRAKES", "complaints": 1}],
    }
    marks = [c["mark"]["type"] for c in charts_for(tables)]
    assert marks == ["bar", "line"]
    assert charts_for({}) == []
