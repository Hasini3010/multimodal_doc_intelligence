"""FastAPI application entrypoint."""



from __future__ import annotations



import json

import logging

from contextlib import asynccontextmanager

from pathlib import Path



from fastapi import FastAPI, File, HTTPException, UploadFile

from fastapi.middleware.cors import CORSMiddleware



from agent.llm_client import (
    LLMClientError,
    LLMRateLimitError,
    LLMUnavailableError,
    get_llm_client,
)

from agent.query_pipeline import ask

from app.config import get_settings

from app.schemas import AskRequest, AskResponse, DocumentSummary, HealthResponse

from ingestion.pipeline import ingest_pdf



logger = logging.getLogger(__name__)





@asynccontextmanager

async def lifespan(app: FastAPI):

    try:

        client = get_llm_client()

        if client.llm_configured():

            client.validate_models_on_startup()

    except Exception as exc:

        logger.warning("LLM startup validation skipped: %s", exc)

    yield





app = FastAPI(

    title="Multimodal Document Intelligence",

    description="HNX26PSI01 — ingest PDFs and answer with cited evidence",

    version="0.3.0",

    lifespan=lifespan,

)



app.add_middleware(

    CORSMiddleware,

    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)





@app.get("/health", response_model=HealthResponse)

def health() -> HealthResponse:

    settings = get_settings()

    client = get_llm_client()

    configured = client.llm_configured()

    status = "ok" if configured else "degraded"

    role_map = settings.model_role_map()

    return HealthResponse(

        status=status,

        gemini_configured=configured,

        models={

            "vlm": role_map.get("vlm", ""),

            "pro": role_map.get("pro", ""),

            "fast": role_map.get("fast", ""),

            "lite": role_map.get("lite", ""),

        },

    )





@app.get("/documents", response_model=list[DocumentSummary])

def list_documents() -> list[DocumentSummary]:

    settings = get_settings()

    index_dir = settings.resolve_path(settings.index_dir)

    out: list[DocumentSummary] = []

    if not index_dir.exists():

        return out

    for doc_dir in index_dir.iterdir():

        if not doc_dir.is_dir() or doc_dir.name.startswith("_"):

            continue

        meta_path = doc_dir / "meta.json"

        if not meta_path.exists():

            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        report = meta.get("report") or {}

        pages = report.get("pages_total") or 0

        out.append(

            DocumentSummary(

                doc_id=meta.get("doc_id", doc_dir.name),

                doc_name=meta.get("doc_name", doc_dir.name),

                page_count=pages,

                sha256=meta.get("sha256"),

            )

        )

    return out





@app.post("/ingest")

async def ingest(file: UploadFile = File(...)) -> dict:

    settings = get_settings()

    upload_dir = settings.resolve_path(settings.data_dir) / "uploads"

    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / (file.filename or "upload.pdf")

    dest.write_bytes(await file.read())

    report = ingest_pdf(dest, settings=settings)

    try:

        from indexing.store import build_document_index



        build_document_index(settings.resolve_path(settings.index_dir), rebuild_vectors=True)

    except Exception:

        pass

    return report.model_dump()





@app.post("/ask", response_model=AskResponse)

def ask_endpoint(body: AskRequest) -> AskResponse:

    client = get_llm_client()

    if not client.llm_configured():

        raise HTTPException(status_code=503, detail={"error": "llm_unavailable"})

    try:

        return ask(body.question, doc_ids=body.doc_ids, client=client)

    except (LLMUnavailableError, LLMRateLimitError, LLMClientError) as exc:
        logger.error("/ask LLM unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_unavailable", "message": str(exc)},
        ) from exc





@app.get("/documents/{doc_id}/pdf")

def get_document_pdf(doc_id: str):

    from fastapi.responses import FileResponse



    settings = get_settings()

    ref_path = settings.resolve_path(settings.index_dir) / doc_id / "source_ref.json"

    if not ref_path.exists():

        raise HTTPException(status_code=404, detail="Document not found")

    ref = json.loads(ref_path.read_text(encoding="utf-8"))

    pdf_path = Path(ref.get("path", ""))

    if not pdf_path.exists():

        raise HTTPException(status_code=404, detail="PDF file missing on disk")

    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)





@app.get("/page/{doc_id}/{page}")

def get_page_image(doc_id: str, page: int):

    from fastapi.responses import FileResponse



    settings = get_settings()

    path = settings.resolve_path(settings.index_dir) / doc_id / "pages" / f"page_{page:03d}.png"

    if not path.exists():

        raise HTTPException(status_code=404, detail="Page image not found")

    return FileResponse(path, media_type="image/png")





@app.get("/element/{element_id}")

def get_element(element_id: str) -> dict:

    settings = get_settings()

    index_dir = settings.resolve_path(settings.index_dir)

    for doc_dir in index_dir.iterdir():

        if not doc_dir.is_dir():

            continue

        el_path = doc_dir / "elements.json"

        if not el_path.exists():

            continue

        rows = json.loads(el_path.read_text(encoding="utf-8"))

        for row in rows:

            if row.get("element_id") == element_id:

                return row

    raise HTTPException(status_code=404, detail="Element not found")

