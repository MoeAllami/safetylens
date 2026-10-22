import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from safetylens.answer.budget import Budget, BudgetExceeded
from safetylens.answer.llm import AnthropicLLM, FakeLLM, LLMError, LLMRefusal, RoleConfig
from safetylens.answer.models import JudgeVerdict, WriterOutput
from safetylens.answer.pricing import UnknownModelPrice, cost_usd

TODAY = dt.date(2026, 1, 2)


def _budget(tmp_path: Path, cap: float, purpose: str = "ask") -> Budget:
    return Budget(tmp_path / "ledger.jsonl", cap, purpose, today=lambda: TODAY)


def test_cost_from_prices() -> None:
    # 1M input at $2 + 100k output at $10 = $3.00
    assert cost_usd("claude-sonnet-5-5", 1_000_000, 100_000) == pytest.approx(3.0)
    # cache reads cost a tenth of input
    assert cost_usd("claude-haiku-5-5", 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.01)
    with pytest.raises(UnknownModelPrice):
        cost_usd("claude-made-up", 1, 1)


def test_budget_blocks_the_call_that_would_cross_the_cap(tmp_path: Path) -> None:
    budget = _budget(tmp_path, cap=1.00)
    budget.record("writer", "claude-sonnet-5-5", 10, 10, 0.95)
    budget.check(0.05)  # exactly at the cap is fine
    with pytest.raises(BudgetExceeded, match="spent \\$0.9500"):
        budget.check(0.06)


def test_caps_are_per_purpose_and_per_day(tmp_path: Path) -> None:
    _budget(tmp_path, 1.0, "eval").record("judge", "claude-sonnet-5-5", 1, 1, 0.99)
    assert _budget(tmp_path, 1.0, "ask").spent_today() == 0.0
    tomorrow = Budget(
        tmp_path / "ledger.jsonl", 1.0, "eval", today=lambda: TODAY + dt.timedelta(days=1)
    )
    assert tomorrow.spent_today() == 0.0


def test_no_cap_configured_means_no_calls(tmp_path: Path) -> None:
    with pytest.raises(BudgetExceeded, match="no ask budget configured"):
        _budget(tmp_path, cap=0.0).check(0.0001)


def test_ledger_holds_no_prompt_text(tmp_path: Path) -> None:
    _budget(tmp_path, 1.0).record("writer", "claude-sonnet-5-5", 120, 30, 0.001)
    entry = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8"))
    assert set(entry) == {
        "date",
        "purpose",
        "role",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    }


class FakeMessages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


def _response(parsed: Any, stop: str = "end_turn", model: str = "claude-sonnet-5-5") -> Any:
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return SimpleNamespace(usage=usage, model=model, stop_reason=stop, parsed_output=parsed)


def _client(response: Any) -> Any:
    plain, beta = FakeMessages(response), FakeMessages(response)
    return SimpleNamespace(messages=plain, beta=SimpleNamespace(messages=beta))


def _llm(tmp_path: Path, client: Any, cap: float = 1.0) -> AnthropicLLM:
    roles = {
        "planner": RoleConfig("claude-haiku-5-5", "low"),
        "writer": RoleConfig("claude-sonnet-5-5", "medium"),
    }
    return AnthropicLLM(roles, _budget(tmp_path, cap), client)  # type: ignore[arg-type]


def test_sonnet_uses_server_side_fallback_and_records_cost(tmp_path: Path) -> None:
    client = _client(_response(WriterOutput(answer_markdown="ok", citations=[])))
    llm = _llm(tmp_path, client)
    out = llm.structured("writer", "sys", "user", WriterOutput, 500)
    assert out.answer_markdown == "ok"
    assert client.beta.messages.kwargs["fallbacks"] == "default"
    assert client.beta.messages.kwargs["output_config"] == {"effort": "medium"}
    assert llm.spent_usd == pytest.approx(0.003)  # 1000 x $2 + 100 x $10 per million
    assert _budget(tmp_path, 1.0).spent_today() == pytest.approx(0.003)


def test_haiku_uses_plain_parse(tmp_path: Path) -> None:
    client = _client(_response(JudgeVerdict(supported=True, reason="x"), model="claude-haiku-5-5"))
    _llm(tmp_path, client).structured("planner", "sys", "user", JudgeVerdict, 500)
    assert client.messages.kwargs["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in client.messages.kwargs


def test_budget_is_checked_before_calling(tmp_path: Path) -> None:
    client = _client(_response(None))
    with pytest.raises(BudgetExceeded):
        _llm(tmp_path, client, cap=0.0000001).structured("writer", "s", "u", WriterOutput, 500)
    assert client.beta.messages.kwargs == {}  # never called


def test_refusal_and_truncation_raise(tmp_path: Path) -> None:
    with pytest.raises(LLMRefusal):
        _llm(tmp_path, _client(_response(None, stop="refusal"))).structured(
            "writer", "s", "u", WriterOutput, 9
        )
    with pytest.raises(LLMError, match="max_tokens"):
        _llm(tmp_path, _client(_response(None, stop="max_tokens"))).structured(
            "writer", "s", "u", WriterOutput, 9
        )
    with pytest.raises(LLMError, match="did not parse"):
        _llm(tmp_path, _client(_response(None))).structured("writer", "s", "u", WriterOutput, 9)


def test_missing_model_name_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SAFETYLENS_WRITER_MODEL"):
        AnthropicLLM({"writer": RoleConfig("", "medium")}, _budget(tmp_path, 1.0), object())  # type: ignore[arg-type]


def test_fake_llm_scripts_and_records() -> None:
    llm = FakeLLM().script("judge", JudgeVerdict(supported=True, reason="a"), RuntimeError("boom"))
    assert llm.structured("judge", "s", "u", JudgeVerdict, 1).supported
    with pytest.raises(RuntimeError):
        llm.structured("judge", "s", "u", JudgeVerdict, 1)
    with pytest.raises(AssertionError, match="no scripted reply"):
        llm.structured("judge", "s", "u", JudgeVerdict, 1)
    assert len(llm.calls) == 3
