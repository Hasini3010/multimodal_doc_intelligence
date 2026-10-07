"""Cross-encoder reranking (bge-reranker-base)."""

from __future__ import annotations

import logging
from functools import lru_cache

from retrieval.hybrid import RetrievalHit

logger = logging.getLogger(__name__)

RERANKER_MODEL = "BAAI/bge-reranker-base"


@lru_cache(maxsize=1)
def _get_reranker():
    from sentence_transformers import CrossEncoder

    logger.info("Loading reranker %s", RERANKER_MODEL)
    return CrossEncoder(RERANKER_MODEL)


def rerank_hits(query: str, hits: list[RetrievalHit], top_k: int = 8) -> list[RetrievalHit]:
    if not hits:
        return []
    if len(hits) <= top_k:
        return hits
    try:
        model = _get_reranker()
        pairs = [(query, h.element.text[:512]) for h in hits]
        scores = model.predict(pairs)
        ranked = sorted(zip(hits, scores), key=lambda x: float(x[1]), reverse=True)
        out: list[RetrievalHit] = []
        for h, sc in ranked[:top_k]:
            h.score = float(sc)
            h.sources["rerank"] = float(sc)
            out.append(h)
        return out
    except Exception as exc:
        logger.warning("Reranker unavailable (%s); using RRF order", exc)
        return hits[:top_k]
