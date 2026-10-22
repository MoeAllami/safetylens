"""A daily spending cap that is checked before every LLM call (gate D13).

Why check before, with a worst-case estimate: checking after the call would let the call that
crosses the cap happen. The ledger is a JSON-lines file with dates, models, token counts and
costs only, never prompts or narratives, so it is safe to keep and to read.
"""

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel


class BudgetExceeded(RuntimeError):
    """The call would take today's spend for this purpose over its cap."""


class LedgerEntry(BaseModel):
    date: dt.date
    purpose: str
    role: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class Budget:
    def __init__(
        self,
        ledger: Path,
        cap_usd: float,
        purpose: str,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self._ledger = ledger
        self._cap = cap_usd
        self._purpose = purpose
        self._today = today

    @property
    def purpose(self) -> str:
        return self._purpose

    def spent_today(self) -> float:
        if not self._ledger.exists():
            return 0.0
        today = self._today()
        total = 0.0
        for line in self._ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = LedgerEntry.model_validate_json(line)
            if entry.date == today and entry.purpose == self._purpose:
                total += entry.cost_usd
        return total

    def check(self, estimate_usd: float) -> None:
        if self._cap <= 0:
            raise BudgetExceeded(f"no {self._purpose} budget configured (cap is {self._cap:.2f})")
        spent = self.spent_today()
        if spent + estimate_usd > self._cap:
            raise BudgetExceeded(
                f"{self._purpose} budget: spent ${spent:.4f} today, this call could cost up to "
                f"${estimate_usd:.4f}, cap ${self._cap:.2f}"
            )

    def record(
        self, role: str, model: str, input_tokens: int, output_tokens: int, cost: float
    ) -> None:
        entry = LedgerEntry(
            date=self._today(),
            purpose=self._purpose,
            role=role,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )
        self._ledger.parent.mkdir(parents=True, exist_ok=True)
        with self._ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.model_dump(mode="json")) + "\n")
