"""BM25 index over element text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@dataclass
class Bm25Index:
    element_ids: list[str] = field(default_factory=list)
    _bm25: BM25Okapi | None = None
    _corpus_tokens: list[list[str]] = field(default_factory=list)

    def build(self, element_ids: list[str], texts: list[str]) -> None:
        self.element_ids = element_ids
        self._corpus_tokens = [tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(self._corpus_tokens)

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if not self._bm25 or not self.element_ids:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(
            zip(self.element_ids, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]
