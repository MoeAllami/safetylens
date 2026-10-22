"""Pydantic contracts for everything that crosses a boundary in the answer pipeline.

Why strict models: the planner and writer are LLMs. Parsing their output into these types (with
the API's structured outputs) means a malformed reply fails loudly here instead of leaking into
SQL parameters or the UI.
"""

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field

Intent = Literal["top_components", "trend", "recalls", "examples", "compare", "out_of_scope"]
Status = Literal["answered", "refused", "clarify", "fallback_template", "budget_exceeded"]


class VehicleRef(BaseModel):
    make: str = Field(description="Manufacturer as the user wrote it, e.g. 'Ford'")
    model: str = Field(description="Model as the user wrote it, e.g. 'F-150'")
    year_from: int | None = Field(default=None, description="First model year, or null")
    year_to: int | None = Field(default=None, description="Last model year, or null")


class QueryPlan(BaseModel):
    intent: Intent
    vehicle: VehicleRef | None = None
    compare_vehicle: VehicleRef | None = None
    component_system: str | None = Field(
        default=None, description="One of the known component systems, or null"
    )
    received_from: str | None = Field(default=None, description="YYYY-MM-DD or null")
    received_to: str | None = Field(default=None, description="YYYY-MM-DD or null")
    search_text: str = Field(default="", description="What to look for in complaint narratives")
    reason: str = Field(default="", description="One short sentence explaining the intent")


class WriterOutput(BaseModel):
    answer_markdown: str
    citations: list[str] = Field(description="Every ODI number or campaign number cited")


class JudgeVerdict(BaseModel):
    supported: bool
    reason: str


class Evidence(BaseModel):
    odino: str
    received_date: dt.date | None
    components: list[str]
    narrative: str


class ResolvedVehicle(BaseModel):
    make: str
    model: str  # display name of the best match
    model_key: str
    year_from: int | None
    year_to: int | None

    @property
    def label(self) -> str:
        years = ""
        if self.year_from and self.year_to:
            years = (
                f"{self.year_from} "
                if self.year_from == self.year_to
                else f"{self.year_from}-{self.year_to} "
            )
        return f"{years}{self.make} {self.model}"


class ComputeResult(BaseModel):
    intent: Intent
    vehicles: list[ResolvedVehicle]
    tables: dict[str, list[dict[str, Any]]]


class Answer(BaseModel):
    question: str
    status: Status
    text: str
    plan: QueryPlan | None = None
    compute: ComputeResult | None = None
    evidence: list[Evidence] = []
    citations: list[str] = []
    first_draft_errors: list[str] = []
    validation_errors: list[str] = []
    clarify_options: list[str] = []
    writer_calls: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
