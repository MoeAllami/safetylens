"""Build the real answer engine from settings (the CLI and the eval runner share this).

Why the key comes from Settings: pydantic-settings reads `.env`, but it does not export it into
the process environment, so the Anthropic client is given the key explicitly here.
"""

from typing import Literal

import anthropic
import duckdb

from safetylens.answer.budget import Budget
from safetylens.answer.llm import AnthropicLLM, Role, RoleConfig
from safetylens.answer.pipeline import Engine
from safetylens.config import Settings
from safetylens.search import embed, rerank

LEDGER = "llm_usage.jsonl"


def build_llm(settings: Settings, purpose: Literal["ask", "eval"]) -> AnthropicLLM:
    cap = settings.daily_budget_usd if purpose == "ask" else settings.eval_budget_usd
    roles: dict[Role, RoleConfig] = {
        "planner": RoleConfig(settings.planner_model, settings.planner_effort),
        "writer": RoleConfig(settings.writer_model, settings.writer_effort),
    }
    if purpose == "eval":
        roles["judge"] = RoleConfig(settings.judge_model, settings.judge_effort)
    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    return AnthropicLLM(
        roles,
        Budget(settings.data_dir / LEDGER, cap, purpose),
        anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic(),
    )


def build_engine(settings: Settings, con: duckdb.DuckDBPyConnection, llm: AnthropicLLM) -> Engine:
    return Engine(
        con=con,
        llm=llm,
        embedder=embed.default_embedder(
            settings.embed_model, settings.embed_device, settings.embed_batch_size
        ),
        reranker=rerank.default_reranker(settings.rerank_model, settings.embed_device),
        rerank_depth=settings.rerank_depth,
    )
