"""Deterministic answers built straight from SQL rows: the safe fallback when the writer fails.

Why it always passes validation: every number is copied from a row and every citation is an id
that was retrieved, so this path can never invent anything. It is also the refusal text for
questions the app should not answer (safety verdicts, buying advice).
"""

from safetylens.answer.models import ComputeResult, Evidence

REFUSAL = (
    "I can't say whether a vehicle is safe or which one to buy: complaints are unverified reports "
    "and counts are not defect rates. I can show what owners report and which recalls exist for a "
    'specific vehicle, for example "What are the most common complaints for a 2022 Ford F-150?" '
    'or "Are there recalls for the 2021 Honda CR-V?"'
)
BUDGET = "The daily budget for answers has been reached. Please try again tomorrow."
ERROR = "Sorry, I couldn't produce a verified answer to this question. Please try rephrasing it."


def _cite(evidence: list[Evidence], topic: str, n: int = 3) -> tuple[str, list[str]]:
    """Name the problem in the citing sentence, so each cited report is cited for something."""
    ids = [e.odino for e in evidence[:n]]
    if not ids:
        return "", []
    # Words with digits ("12-volt") are dropped: every number in a template must come from SQL.
    words = [w for w in topic.split() if not any(ch.isdigit() for ch in w)]
    about = f" describing {' '.join(words)}" if words else ""
    return f"Example reports{about}: " + " ".join(f"[{i}]" for i in ids) + ".", ids


def template_answer(
    result: ComputeResult, evidence: list[Evidence], topic: str = ""
) -> tuple[str, list[str]]:
    lines: list[str] = []
    citations: list[str] = []
    counts = {r["vehicle"]: r["complaints"] for r in result.tables.get("complaint_count", [])}
    for vehicle, n in counts.items():
        lines.append(f"{vehicle}: {n} distinct complaints match.")
    if result.intent in ("top_components", "compare"):
        for vehicle in counts:
            top = [r for r in result.tables.get("top_components", []) if r["vehicle"] == vehicle][
                :3
            ]
            if top:
                parts = ", ".join(f"{r['component']} ({r['complaints']})" for r in top)
                lines.append(f"Most reported components for {vehicle}: {parts}.")
    elif result.intent == "trend":
        months = result.tables.get("monthly_trend", [])
        if months:
            peak = max(months, key=lambda r: r["complaints"])
            lines.append(
                f"The busiest month was {peak['month'][:7]} with {peak['complaints']} complaints."
            )
    elif result.intent == "recalls":
        recalls = result.tables.get("recalls", [])
        if not recalls:
            lines.append("No recall campaigns match.")
        for r in recalls[:8]:
            lines.append(
                f"[{r['campno']}] {', '.join(r['components'])} (reported {r['report_date']})."
            )
            citations.append(str(r["campno"]))
    if result.intent != "recalls":
        text, ids = _cite(evidence, topic)
        if text:
            lines.append(text.strip())
            citations += ids
    return "\n\n".join(lines), citations
