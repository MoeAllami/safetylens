"""The answer pipeline: plan -> resolve -> SQL -> retrieve -> write -> validate -> answer.

Why the fallbacks: each step that can fail (budget, refusal, a reply that does not validate) falls
back to a deterministic template built from SQL rows, so a user always gets something correct.
"""

import datetime as dt
import json
import time
from dataclasses import dataclass

import duckdb

from safetylens.answer import prompts
from safetylens.answer.budget import BudgetExceeded
from safetylens.answer.compute import allowed_numbers, compute, known_systems, vehicle_filter
from safetylens.answer.llm import LLM, LLMError, LLMRefusal
from safetylens.answer.models import (
    Answer,
    ComputeResult,
    Evidence,
    QueryPlan,
    ResolvedVehicle,
    VehicleRef,
    WriterOutput,
)
from safetylens.answer.resolver import resolve
from safetylens.answer.template import BUDGET, REFUSAL, template_answer
from safetylens.answer.validator import validate
from safetylens.search.embed import Embedder
from safetylens.search.rerank import Reranker
from safetylens.search.search import search
from safetylens.store.sql import load_sql

NARRATIVE_CHARS = 1200
EVIDENCE_K = 8
RETRIEVE_INTENTS = ("top_components", "trend", "examples", "compare")


@dataclass
class Engine:
    con: duckdb.DuckDBPyConnection
    llm: LLM
    embedder: Embedder
    reranker: Reranker
    rerank_depth: int = 20
    today: dt.date | None = None

    def _planner_system(self) -> str:
        lo, hi = self.con.execute(load_sql("data_coverage")).fetchone() or (None, None)
        return prompts.PLANNER.format(
            today=(self.today or dt.date.today()).isoformat(),
            coverage=f"complaints received {lo} to {hi}",
            systems="\n".join(known_systems(self.con)),
        )

    def _evidence(
        self, plan: QueryPlan, question: str, vehicles: list[ResolvedVehicle]
    ) -> list[Evidence]:
        if plan.intent not in RETRIEVE_INTENTS:
            return []
        k = EVIDENCE_K // len(vehicles)
        ids: list[str] = []
        for v in vehicles:
            f = vehicle_filter(v, plan, plan.component_system)
            hits = search(
                self.con,
                f,
                plan.search_text or question,
                method="rerank",
                k=k,
                embedder=self.embedder,
                reranker=self.reranker,
                rerank_depth=self.rerank_depth,
            )
            ids += [h.odino for h in hits]
        rows = self.con.execute(load_sql("evidence_for"), {"odinos": ids}).fetchall()
        return [
            Evidence(
                odino=str(r[0]),
                received_date=r[1],
                components=list(r[2]),
                narrative=str(r[3])[:NARRATIVE_CHARS],
            )
            for r in rows
        ]

    def _writer_prompt(self, question: str, result: ComputeResult, evidence: list[Evidence]) -> str:
        payload = {
            "question": question,
            "vehicles": [v.label for v in result.vehicles],
            "sql_results": result.tables,
            "complaints": [e.model_dump(mode="json") for e in evidence],
            "citable_ids": sorted(self._citable(result, evidence)),
        }
        return json.dumps(payload, indent=1, default=str)

    @staticmethod
    def _citable(result: ComputeResult, evidence: list[Evidence]) -> set[str]:
        ids = {e.odino for e in evidence}
        return ids | {str(r["campno"]) for r in result.tables.get("recalls", [])}

    def ask(self, question: str) -> Answer:
        started, spent = time.perf_counter(), self.llm.spent_usd
        answer = self._ask(question)
        answer.latency_s = time.perf_counter() - started
        answer.cost_usd = self.llm.spent_usd - spent
        return answer

    def _ask(self, question: str) -> Answer:
        try:
            plan = self.llm.structured("planner", self._planner_system(), question, QueryPlan, 1500)
        except BudgetExceeded:
            return Answer(question=question, status="budget_exceeded", text=BUDGET)
        except (LLMRefusal, LLMError):
            return Answer(question=question, status="refused", text=REFUSAL)
        if plan.intent == "out_of_scope" or plan.vehicle is None:
            return Answer(question=question, status="refused", text=REFUSAL, plan=plan)
        first = plan.vehicle
        if plan.component_system not in known_systems(self.con):
            plan = plan.model_copy(
                update={"component_system": None}
            )  # never filter on an invented name

        refs: list[VehicleRef] = [first]
        if plan.intent == "compare" and plan.compare_vehicle is not None:
            refs.append(plan.compare_vehicle)
        vehicles: list[ResolvedVehicle] = []
        for ref in refs:
            res = resolve(self.con, ref)
            if res.status != "ok" or res.vehicle is None:
                text = "Which vehicle did you mean? " + "; ".join(res.options)
                return Answer(
                    question=question,
                    status="clarify",
                    text=text,
                    plan=plan,
                    clarify_options=res.options,
                )
            vehicles.append(res.vehicle)

        result = compute(self.con, plan, vehicles)
        evidence = self._evidence(plan, question, vehicles)
        numbers = allowed_numbers(result, plan)
        citable = self._citable(result, evidence)
        base = Answer(
            question=question,
            status="answered",
            text="",
            plan=plan,
            compute=result,
            evidence=evidence,
        )

        user = self._writer_prompt(question, result, evidence)
        for attempt in range(2):
            try:
                draft = self.llm.structured("writer", prompts.WRITER, user, WriterOutput, 4000)
            except (BudgetExceeded, LLMRefusal, LLMError):
                break
            base.writer_calls += 1
            errors = validate(self.con, draft.answer_markdown, draft.citations, numbers, citable)
            if attempt == 0:
                base.first_draft_errors = errors
            if not errors:
                base.text, base.citations, base.validation_errors = (
                    draft.answer_markdown,
                    draft.citations,
                    [],
                )
                return base
            base.validation_errors = errors
            user += "\n\n" + prompts.RETRY.format(errors="\n".join(f"- {e}" for e in errors))

        topic = plan.search_text or (plan.component_system or "").lower()
        base.text, base.citations = template_answer(result, evidence, topic)
        base.status = "fallback_template"
        return base
