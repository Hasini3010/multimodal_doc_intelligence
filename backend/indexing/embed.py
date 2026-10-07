"""Dense embeddings with BAAI/bge-m3 (local CPU)."""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-m3"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %s (first run may download weights)", MODEL_NAME)
    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
