"""Golden-question eval (gates D5, D6, D7, D9, D13): run each question, score it, write a report.

Why facts are checked on structured results: whether the answer found the right vehicle, the right
top component or the right recall is decided from the plan and SQL rows, not by grading prose.
Prose is checked only for grounding (numbers, citations) and, by a judge model, for whether each
cited complaint supports the sentence that cites it.
"""

import datetime as dt
import re
from pathlib import Path
from statistics import mean, quantiles
from typing import Any

import duckdb
import yaml
from pydantic import BaseModel

from safetylens.answer import prompts
from safetylens.answer.compute import allowed_numbers
from safetylens.answer.llm import LLM
from safetylens.answer.models import Answer, Intent, JudgeVerdict
from safetylens.answer.numbers import citations_in
from safetylens.answer.pipeline import Engine
from safetylens.answer.validator import validate

TARGETS = {
    "numbers_grounded": 1.0,
    "citations_valid": 1.0,
    "citations_supportive": 0.90,
    "golden_pass": 0.85,
}
JUDGE_CHARS = 1500
REVIEW_CHARS = 400


class GoldenItem(BaseModel):
    id: str
    question: str
    intent: Intent
    expected_facts: dict[str, Any] = {}
    must_cite: bool = True
    notes: str = ""


class Verdict(BaseModel):
    """One judged citation, kept for the owner's spot-check (written only to git-ignored data/)."""

    item_id: str
    odino: str
    claim: str
    supported: bool
    reason: str
    narrative_excerpt: str


class ItemResult(BaseModel):
    id: str
    intent_expected: Intent
    status: str
    passed: bool
    failures: list[str]
    grounded: bool | None
    citations_valid: bool | None
    supported: int
    judged: int
    first_draft_ok: bool | None
    latency_s: float
    cost_usd: float
    verdicts: list[Verdict] = []
    first_draft_errors: list[str] = []


class GoldenReport(BaseModel):
    date: dt.date
    items: list[ItemResult]
    judge_cost_usd: float

    def _rate(self, values: list[bool]) -> float:
        return sum(values) / len(values) if values else 1.0

    def metrics(self) -> dict[str, float]:
        answered = [i for i in self.items if i.grounded is not None]
        oos = [i for i in self.items if i.intent_expected == "out_of_scope"]
        judged = sum(i.judged for i in self.items)
        lat = [i.latency_s for i in self.items]
        return {
            "numbers_grounded": self._rate([bool(i.grounded) for i in answered]),
            "citations_valid": self._rate([bool(i.citations_valid) for i in answered]),
            "citations_supportive": sum(i.supported for i in self.items) / judged
            if judged
            else 1.0,
            "golden_pass": self._rate([i.passed for i in self.items]),
            "refusals_correct": float(sum(i.passed for i in oos)),
            "refusals_total": float(len(oos)),
            "first_draft_ok": self._rate([bool(i.first_draft_ok) for i in answered]),
            "p50_latency_s": quantiles(lat, n=100)[49]
            if len(lat) > 1
            else (lat[0] if lat else 0.0),
            "p95_latency_s": quantiles(lat, n=100)[94]
            if len(lat) > 1
            else (lat[0] if lat else 0.0),
            "mean_cost_usd": mean(i.cost_usd for i in self.items) if self.items else 0.0,
        }

    def passed(self) -> bool:
        m = self.metrics()
        return (
            all(m[k] >= v for k, v in TARGETS.items())
            and m["refusals_correct"] == m["refusals_total"]
        )


def load_golden(path: Path) -> list[GoldenItem]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [GoldenItem.model_validate(item) for item in data["items"]]


def check_facts(item: GoldenItem, answer: Answer) -> list[str]:
    """Compare expected facts with the plan and SQL rows; returns what did not match."""
    failures: list[str] = []
    tables = answer.compute.tables if answer.compute else {}
    for key, want in item.expected_facts.items():
        got: Any
        if key == "status":
            got = answer.status
        elif key == "resolved":
            got = (
                [f"{v.make} {v.model_key}" for v in answer.compute.vehicles]
                if answer.compute
                else []
            )
            ok = want in got if isinstance(want, str) else sorted(want) == sorted(got)
            if not ok:
                failures.append(f"resolved: want {want}, got {got}")
            continue
        elif key == "component_system":
            got = answer.plan.component_system if answer.plan else None
        elif key == "top_component":
            rows = tables.get("top_components", [])
            got = rows[0]["component"] if rows else None
        elif key == "distinct_complaints":
            got = [r["complaints"] for r in tables.get("complaint_count", [])]
            got = got[0] if len(got) == 1 else got
        elif key == "campaign_in_results":
            got_ids = {r["campno"] for r in tables.get("recalls", [])}
            if want not in got_ids:
                failures.append(f"campaign_in_results: {want} not in {len(got_ids)} campaigns")
            continue
        elif key == "campaigns_total":
            rows = tables.get("recalls", [])
            got = rows[0]["campaigns_total"] if rows else 0
        elif key == "peak_month":
            months = tables.get("monthly_trend", [])
            got = max(months, key=lambda r: r["complaints"])["month"][:7] if months else None
        else:
            failures.append(f"unknown expected fact {key!r}")
            continue
        if isinstance(want, list) and isinstance(got, list):
            got, want = sorted(got), sorted(want)  # compare items: vehicle order doesn't matter
        if got != want:
            failures.append(f"{key}: want {want}, got {got}")
    return failures


def _claims(text: str) -> dict[str, str]:
    """Each cited complaint id -> the sentence or bullet line that cites it."""
    claims: dict[str, str] = {}
    for line in text.splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            for cid in citations_in(sentence):
                if not re.fullmatch(r"\d{6,9}", cid):
                    continue  # recall campaigns are checked structurally, not judged
                claims.setdefault(cid, sentence.strip())
    return claims


def judge_citations(llm: LLM, answer: Answer, item_id: str = "") -> list[Verdict]:
    narratives = {e.odino: e.narrative for e in answer.evidence}
    verdicts: list[Verdict] = []
    for cid, claim in _claims(answer.text).items():
        narrative = narratives.get(cid, "")[:JUDGE_CHARS]
        user = f"Claim: {claim}\n\nCited complaint [{cid}]:\n{narrative}"
        verdict = llm.structured("judge", prompts.JUDGE, user, JudgeVerdict, 600)
        verdicts.append(
            Verdict(
                item_id=item_id,
                odino=cid,
                claim=claim,
                supported=verdict.supported,
                reason=verdict.reason,
                narrative_excerpt=narrative[:REVIEW_CHARS],
            )
        )
    return verdicts


def score_item(
    con: duckdb.DuckDBPyConnection, llm: LLM, item: GoldenItem, answer: Answer
) -> ItemResult:
    failures = check_facts(item, answer)
    grounded = valid = first_ok = None
    supported = judged = 0
    verdicts: list[Verdict] = []
    if item.intent == "out_of_scope":
        if answer.status != "refused" or answer.citations:
            failures.append(f"expected a refusal with no citations, got {answer.status}")
    elif answer.status in ("answered", "fallback_template") and answer.compute and answer.plan:
        if answer.plan.intent != item.intent:
            failures.append(f"intent: want {item.intent}, got {answer.plan.intent}")
        citable = {e.odino for e in answer.evidence} | {
            str(r["campno"]) for r in answer.compute.tables.get("recalls", [])
        }
        errors = validate(
            con,
            answer.text,
            answer.citations,
            allowed_numbers(answer.compute, answer.plan),
            citable,
        )
        grounded = not any(e.startswith("numbers") for e in errors)
        valid = not any(e.startswith("citations") or e.startswith("cited") for e in errors)
        first_ok = not answer.first_draft_errors
        failures += errors
        if item.must_cite and not answer.citations:
            failures.append("no citations")
        verdicts = judge_citations(llm, answer, item.id)
        judged, supported = len(verdicts), sum(v.supported for v in verdicts)
        if judged and supported < judged:
            failures.append(f"citations supportive {supported}/{judged}")
    elif "status" not in item.expected_facts:
        failures.append(f"status {answer.status}")
    return ItemResult(
        id=item.id,
        intent_expected=item.intent,
        status=answer.status,
        passed=not failures,
        failures=failures,
        grounded=grounded,
        citations_valid=valid,
        supported=supported,
        judged=judged,
        verdicts=verdicts,
        first_draft_ok=first_ok,
        first_draft_errors=answer.first_draft_errors,
        latency_s=answer.latency_s,
        cost_usd=answer.cost_usd,
    )


def run_golden(
    engine: Engine, items: list[GoldenItem], today: dt.date | None = None
) -> GoldenReport:
    results: list[ItemResult] = []
    judge_cost = 0.0
    for item in items:
        answer = engine.ask(item.question)
        before = engine.llm.spent_usd
        results.append(score_item(engine.con, engine.llm, item, answer))
        judge_cost += engine.llm.spent_usd - before
    return GoldenReport(date=today or dt.date.today(), items=results, judge_cost_usd=judge_cost)
