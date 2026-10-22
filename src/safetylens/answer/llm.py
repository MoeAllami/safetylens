"""The only place that talks to Claude: structured calls for the planner, writer and judge.

Why one narrow interface: every call goes through the budget check, the cost ledger and the
refusal check in one spot, and tests swap in FakeLLM (CLAUDE.md rule 7) without touching the
pipeline. Model names come from settings; nothing here picks a model.
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

import anthropic
import structlog
from pydantic import BaseModel

from safetylens.answer.budget import Budget
from safetylens.answer.pricing import cost_usd, price

log = structlog.get_logger()

Role = Literal["planner", "writer", "judge"]
T = TypeVar("T", bound=BaseModel)

# Models that accept the server-side refusal fallback ("default" form) on the Claude API.
FALLBACK_CAPABLE = frozenset(
    {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
)
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMRefusal(RuntimeError):
    """The model (and any fallback) declined the request."""


class LLMError(RuntimeError):
    """The reply could not be used (truncated or failed to parse)."""


class LLM(Protocol):
    spent_usd: float

    def structured(
        self, role: Role, system: str, user: str, schema: type[T], max_tokens: int
    ) -> T: ...


@dataclass
class RoleConfig:
    model: str
    effort: str


def _estimate_usd(model: str, system: str, user: str, max_tokens: int) -> float:
    """Worst case: ~1 token per 3 characters of prompt, plus every allowed output token."""
    per_in, per_out = price(model)
    input_tokens = (len(system) + len(user)) // 3 + 200
    return (input_tokens * per_in + max_tokens * per_out) / 1_000_000


class AnthropicLLM:
    def __init__(
        self,
        roles: dict[Role, RoleConfig],
        budget: Budget,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        for role, cfg in roles.items():
            if not cfg.model:
                raise ValueError(
                    f"no model configured for {role}; set SAFETYLENS_{role.upper()}_MODEL"
                )
        self._roles = roles
        self._budget = budget
        self._client = client or anthropic.Anthropic()
        self.spent_usd = 0.0

    def structured(self, role: Role, system: str, user: str, schema: type[T], max_tokens: int) -> T:
        cfg = self._roles[role]
        self._budget.check(_estimate_usd(cfg.model, system, user, max_tokens))
        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_format": schema,
            "output_config": {"effort": cfg.effort},
        }
        if cfg.model in FALLBACK_CAPABLE:
            response: Any = self._client.beta.messages.parse(
                betas=[FALLBACK_BETA], fallbacks="default", **kwargs
            )
        else:
            response = self._client.messages.parse(**kwargs)
        usage = response.usage
        served_by = str(response.model)
        cost = cost_usd(
            served_by,
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_input_tokens or 0,
            usage.cache_creation_input_tokens or 0,
        )
        self._budget.record(role, served_by, usage.input_tokens, usage.output_tokens, cost)
        self.spent_usd += cost
        log.info(
            "llm_call",
            role=role,
            model=served_by,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=round(cost, 6),
            stop=response.stop_reason,
        )
        if response.stop_reason == "refusal":
            raise LLMRefusal(f"{role} call refused")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"{role} reply hit max_tokens={max_tokens}")
        parsed = response.parsed_output
        if not isinstance(parsed, schema):
            raise LLMError(f"{role} reply did not parse as {schema.__name__}")
        return parsed


Responder = Callable[[str, str], BaseModel]


@dataclass
class FakeLLM:
    """Scripted stand-in for tests: each role pops the next scripted reply (object or callable)."""

    replies: dict[str, deque[BaseModel | Responder | Exception]] = field(default_factory=dict)
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    cost_per_call: float = 0.001
    spent_usd: float = 0.0

    def script(self, role: Role, *replies: BaseModel | Responder | Exception) -> "FakeLLM":
        self.replies.setdefault(role, deque()).extend(replies)
        return self

    def structured(self, role: Role, system: str, user: str, schema: type[T], max_tokens: int) -> T:
        self.calls.append((role, system, user))
        queue = self.replies.get(role)
        if not queue:
            raise AssertionError(f"FakeLLM has no scripted reply left for {role}")
        reply = queue.popleft()
        self.spent_usd += self.cost_per_call
        if isinstance(reply, Exception):
            raise reply
        value = (
            reply(system, user) if callable(reply) and not isinstance(reply, BaseModel) else reply
        )
        if not isinstance(value, schema):
            raise AssertionError(
                f"scripted {role} reply is {type(value).__name__}, not {schema.__name__}"
            )
        return value
