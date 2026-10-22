"""Turn text into vectors so that similar meanings land close together.

Why a protocol with two implementations: the real model needs a download and (ideally) a GPU,
while unit tests must run offline in milliseconds (CLAUDE.md rule 7). Both produce unit-length
vectors of EMBED_DIM numbers, so cosine similarity is just a dot product either way.
"""

import math
import re
import zlib
from collections.abc import Sequence
from typing import Protocol

EMBED_DIM = 384  # bge-small-en-v1.5; the dense search SQL casts to FLOAT[384]
# bge models are trained with this instruction on the query side only, never on documents.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic bag-of-words vectors for tests: shared words give similar vectors."""

    name = "hashing-test-embedder"

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * EMBED_DIM
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            vec[zlib.crc32(token.encode()) % EMBED_DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class SentenceTransformerEmbedder:
    """The real model (bge-small-en-v1.5 by default), on CUDA when available."""

    def __init__(self, model_name: str, *, device: str = "auto", batch_size: int = 128) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, only when used

        self.name = model_name
        self._batch_size = batch_size
        self._model = SentenceTransformer(model_name, device=None if device == "auto" else device)
        dim = self._model.get_embedding_dimension()
        if dim != EMBED_DIM:
            raise ValueError(f"{model_name} produces {dim}-d vectors; search expects {EMBED_DIM}")

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        result: list[list[float]] = vectors.tolist()
        return result

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([BGE_QUERY_PREFIX + text])[0]


def default_embedder(model_name: str, device: str, batch_size: int) -> Embedder:
    """The embedder the CLI uses; tests replace this function with one returning HashingEmbedder."""
    return SentenceTransformerEmbedder(model_name, device=device, batch_size=batch_size)
