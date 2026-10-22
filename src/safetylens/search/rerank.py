"""Reorder the best few candidates by reading each (query, narrative) pair together.

Why a second stage: BM25 and embeddings score query and document separately, which is fast enough
for a whole vehicle but loses detail. A cross-encoder looks at both texts at once and judges the
match much better, but is too slow for 1,000 documents, so it only reorders the fused top few.
"""

import re
from collections.abc import Sequence
from typing import Protocol


class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class OverlapReranker:
    """Deterministic test double: score = how many query words appear in the text."""

    name = "overlap-test-reranker"

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        words = set(re.findall(r"[a-z0-9]+", query.lower()))
        return [float(len(words & set(re.findall(r"[a-z0-9]+", t.lower())))) for t in texts]


class CrossEncoderReranker:
    """The real model (BAAI/bge-reranker-base by default), on CUDA when available."""

    def __init__(self, model_name: str, *, device: str = "auto", max_length: int = 512) -> None:
        from sentence_transformers import CrossEncoder  # heavy import, only when used

        self.name = model_name
        self._model = CrossEncoder(
            model_name, device=None if device == "auto" else device, max_length=max_length
        )

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        scores = self._model.predict([(query, t) for t in texts], show_progress_bar=False)
        return [float(s) for s in scores]


def default_reranker(model_name: str, device: str) -> Reranker:
    """The reranker the CLI uses; tests replace this function with one returning OverlapReranker."""
    return CrossEncoderReranker(model_name, device=device)
