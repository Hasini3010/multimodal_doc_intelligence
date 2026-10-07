"""Hybrid retrieval: dense + BM25 fused with RRF."""

from __future__ import annotations

from dataclasses import dataclass

from indexing.embed import embed_texts
from indexing.store import DocumentIndex, IndexedElement


@dataclass
class RetrievalHit:
    element_id: str
    score: float
    element: IndexedElement
    sources: dict[str, float]


def rrf_fuse(ranked_lists: list[list[tuple[str, float]]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (eid, _raw) in enumerate(ranked):
            scores[eid] = scores.get(eid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_search(
    index: DocumentIndex,
    query: str,
    *,
    top_k: int = 20,
    doc_ids: list[str] | None = None,
) -> list[RetrievalHit]:
    by_id = index.element_by_id()
    allowed = set(doc_ids) if doc_ids else None

    bm25_ranked = index.bm25.search(query, top_k=top_k * 2)
    dense_ranked: list[tuple[str, float]] = []
    if index.chroma_collection is not None:
        qv = embed_texts([query])[0]
        res = index.chroma_collection.query(query_embeddings=[qv], n_results=min(top_k * 2, max(1, len(by_id))))
        ids = res.get("ids", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for eid, dist in zip(ids, dists):
            dense_ranked.append((eid, 1.0 - float(dist)))

    fused = rrf_fuse([bm25_ranked, dense_ranked])
    hits: list[RetrievalHit] = []
    for eid, score in sorted(fused.items(), key=lambda x: x[1], reverse=True):
        el = by_id.get(eid)
        if not el:
            continue
        if allowed is not None and el.doc_name not in allowed:
            continue
        bm25_s = next((s for i, s in bm25_ranked if i == eid), 0.0)
        dense_s = next((s for i, s in dense_ranked if i == eid), 0.0)
        hits.append(
            RetrievalHit(
                element_id=eid,
                score=score,
                element=el,
                sources={"rrf": score, "bm25": bm25_s, "dense": dense_s},
            )
        )
        if len(hits) >= top_k:
            break
    return hits
