"""Vector store (ChromaDB local) + unified index manifest."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from indexing.bm25 import Bm25Index
from indexing.embed import embed_texts

logger = logging.getLogger(__name__)


@dataclass
class IndexedElement:
    element_id: str
    doc_id: str
    doc_name: str
    page: int
    type: str
    section: str | None
    text: str
    bbox: dict
    crop_path: str | None = None
    table_markdown: str | None = None
    figure_json: dict | None = None


@dataclass
class DocumentIndex:
    elements: list[IndexedElement] = field(default_factory=list)
    bm25: Bm25Index = field(default_factory=Bm25Index)
    chroma_collection: object | None = None
    persist_dir: Path | None = None

    def element_by_id(self) -> dict[str, IndexedElement]:
        return {e.element_id: e for e in self.elements}


def element_search_text(raw: dict) -> str:
    parts = [
        raw.get("text") or "",
        raw.get("table_markdown") or "",
        raw.get("section") or "",
        raw.get("doc_name") or "",
    ]
    fig = raw.get("figure_json")
    if isinstance(fig, dict):
        parts.append(json.dumps(fig))
    vlm_text = raw.get("vlm_index_text")
    if vlm_text:
        parts.append(vlm_text)
    return "\n".join(p for p in parts if p).strip() or "(empty)"


def load_elements_from_index(index_dir: Path) -> list[dict]:
    rows: list[dict] = []
    if not index_dir.exists():
        return rows
    for doc_dir in index_dir.iterdir():
        if not doc_dir.is_dir() or doc_dir.name.startswith("_"):
            continue
        el_path = doc_dir / "elements.json"
        if el_path.exists():
            rows.extend(json.loads(el_path.read_text(encoding="utf-8")))
    return rows


def build_document_index(index_dir: Path, *, rebuild_vectors: bool = True) -> DocumentIndex:
    raw_rows = load_elements_from_index(index_dir)
    elements: list[IndexedElement] = []
    for raw in raw_rows:
        text = element_search_text(raw)
        elements.append(
            IndexedElement(
                element_id=raw["element_id"],
                doc_id=raw["doc_id"],
                doc_name=raw["doc_name"],
                page=raw["page"],
                type=raw["type"],
                section=raw.get("section"),
                text=text,
                bbox=raw["bbox"],
                crop_path=raw.get("crop_path"),
                table_markdown=raw.get("table_markdown"),
                figure_json=raw.get("figure_json"),
            )
        )

    ids = [e.element_id for e in elements]
    texts = [e.text for e in elements]
    bm25 = Bm25Index()
    if ids:
        bm25.build(ids, texts)

    doc_index = DocumentIndex(elements=elements, bm25=bm25, persist_dir=index_dir)
    if rebuild_vectors and elements:
        _build_chroma(doc_index, index_dir, ids, texts)
    return doc_index


def _build_chroma(
    doc_index: DocumentIndex, index_dir: Path, ids: list[str], texts: list[str]
) -> None:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    persist = index_dir / "chroma"
    persist.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(persist),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name="elements",
        metadata={"hnsw:space": "cosine"},
    )

    vectors = embed_texts(texts)
    # Chroma upsert in batches
    batch = 64
    for i in range(0, len(ids), batch):
        sl = slice(i, i + batch)
        collection.upsert(
            ids=ids[sl],
            embeddings=vectors[sl],
            documents=texts[sl],
        )
    doc_index.chroma_collection = collection
    manifest = {
        "count": len(ids),
        "embedding_model": "BAAI/bge-m3",
    }
    (index_dir / "vector_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def load_document_index(index_dir: Path) -> DocumentIndex:
    manifest_path = index_dir / "vector_manifest.json"
    if not manifest_path.exists():
        return build_document_index(index_dir, rebuild_vectors=True)

    doc_index = build_document_index(index_dir, rebuild_vectors=False)
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    persist = index_dir / "chroma"
    client = chromadb.PersistentClient(
        path=str(persist),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    doc_index.chroma_collection = client.get_or_create_collection(name="elements")
    return doc_index
