from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent.llm_client import (
    LLMClient,
    LLMClientError,
    LLMRateLimitError,
    LLMUnavailableError,
    get_llm_client,
)
from agent.llm_schemas import AnswererOutput, VlmAnswerExtraction
from agent.prompts import ANSWERER_SYSTEM, VLM_ANSWER_EXTRACT_SYSTEM
from app.schemas import AskResponse, BBox, CalculationResult, Claim, Citation
from retrieval.hybrid import RetrievalHit
from tools.calc import CalcError, evaluate_expression

logger = logging.getLogger(__name__)

ABSTAIN = "not found in the provided documents"


def _format_text_context(hits: list[RetrievalHit]) -> str:
    blocks: list[str] = []
    for h in hits:
        e = h.element
        if e.type in ("figure",) and e.crop_path:
            continue
        body = e.text[:2000]
        if e.type == "table" and e.table_markdown:
            body = f"{body}\n\n{e.table_markdown[:3000]}"
        blocks.append(
            f"[element_id={e.element_id} doc={e.doc_name} page={e.page} "
            f"section={e.section or ''} type={e.type}]\n{body}"
        )
    return "\n\n".join(blocks)


def _visual_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    out: list[RetrievalHit] = []
    seen: set[str] = set()
    for h in hits:
        e = h.element
        if not e.crop_path or e.element_id in seen:
            continue
        p = Path(e.crop_path)
        if not p.exists():
            continue
        if e.type not in ("figure", "table"):
            continue
        seen.add(e.element_id)
        out.append(h)
    return out


def _merge_extractions(a: VlmAnswerExtraction, b: VlmAnswerExtraction) -> VlmAnswerExtraction:
    va = (a.extracted_values or "").strip()
    vb = (b.extracted_values or "").strip()
    if va == vb:
        merged_values = va
    elif not va:
        merged_values = vb
    elif not vb:
        merged_values = va
    else:
        lines_a = {ln.strip() for ln in va.splitlines() if ln.strip()}
        lines_b = {ln.strip() for ln in vb.splitlines() if ln.strip()}
        common = sorted(lines_a & lines_b)
        merged_values = "\n".join(common) if common else va
    return VlmAnswerExtraction(
        element_id=a.element_id or b.element_id,
        extracted_values=merged_values,
        units=a.units or b.units,
        trend_summary=a.trend_summary or b.trend_summary,
        uncertain=False,
    )


def _extract_one_visual(
    hit: RetrievalHit,
    question: str,
    client: LLMClient,
) -> VlmAnswerExtraction | None:
    e = hit.element
    crop = Path(e.crop_path or "")
    if not crop.exists():
        return None
    image_bytes = crop.read_bytes()
    user_msg = (
        f"Question: {question}\n\n"
        f"element_id={e.element_id} doc={e.doc_name} page={e.page} "
        f"section={e.section or ''} type={e.type}\n"
        "Extract only what is visible in this image."
    )

    def _call() -> VlmAnswerExtraction:
        res = client.chat(
            [
                {"role": "system", "content": VLM_ANSWER_EXTRACT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            model_role="vlm",
            images=[(image_bytes, "image/png")],
            json_schema=VlmAnswerExtraction,
        )
        if isinstance(res.parsed, VlmAnswerExtraction):
            parsed = res.parsed
        else:
            parsed = VlmAnswerExtraction.model_validate_json(res.text)
        if not parsed.element_id:
            parsed.element_id = e.element_id
        return parsed

    try:
        first = _call()
    except (LLMRateLimitError, LLMUnavailableError, LLMClientError):
        raise
    except Exception as exc:
        logger.warning("VLM extract failed for %s: %s", e.element_id, exc)
        return None

    if not first.uncertain:
        return first
    try:
        second = _call()
    except Exception as exc:
        logger.warning("VLM re-extract failed for %s: %s", e.element_id, exc)
        return first
    return _merge_extractions(first, second)


def extract_visual_evidence(
    question: str,
    hits: list[RetrievalHit],
    *,
    client: LLMClient,
) -> list[VlmAnswerExtraction]:
    visual = _visual_hits(hits)
    if not visual:
        return []

    extractions: list[VlmAnswerExtraction] = []
    max_workers = min(len(visual), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_extract_one_visual, h, question, client): h for h in visual
        }
        for fut in as_completed(futures):
            try:
                row = fut.result()
            except (LLMRateLimitError, LLMUnavailableError, LLMClientError):
                raise
            except Exception as exc:
                logger.warning("Parallel VLM extract error: %s", exc)
                continue
            if row is not None:
                extractions.append(row)
    return extractions


def _format_vlm_context(extractions: list[VlmAnswerExtraction], hits: list[RetrievalHit]) -> str:
    by_id = {h.element_id: h.element for h in hits}
    blocks: list[str] = []
    for ex in extractions:
        el = by_id.get(ex.element_id)
        doc = el.doc_name if el else "?"
        page = el.page if el else 0
        section = (el.section or "") if el else ""
        etype = el.type if el else "figure"
        blocks.append(
            f"[element_id={ex.element_id} doc={doc} page={page} section={section} "
            f"type={etype} source=vlm_extraction]\n"
            f"units: {ex.units}\n"
            f"trend: {ex.trend_summary}\n"
            f"values:\n{ex.extracted_values}"
        )
    return "\n\n".join(blocks)


def answer_question(
    question: str,
    hits: list[RetrievalHit],
    *,
    client: LLMClient | None = None,
) -> AskResponse:
    client = client or get_llm_client()
    if not hits:
        return AskResponse(answer=ABSTAIN, confidence=0.0, abstained=True)

    vlm_blocks = extract_visual_evidence(question, hits, client=client)
    text_ctx = _format_text_context(hits)
    vlm_ctx = _format_vlm_context(vlm_blocks, hits)
    parts = [p for p in (text_ctx, vlm_ctx) if p.strip()]
    context = "\n\n".join(parts)
    user_msg = f"Question: {question}\n\nEvidence:\n{context}"

    try:
        res = client.chat(
            [
                {"role": "system", "content": ANSWERER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            model_role="pro",
            images=None,
            json_schema=AnswererOutput,
        )
        if isinstance(res.parsed, AnswererOutput):
            data = res.parsed
        else:
            data = AnswererOutput.model_validate_json(res.text)
    except (LLMRateLimitError, LLMUnavailableError, LLMClientError):
        raise
    except Exception as exc:
        logger.error("Answerer failed: %s", exc)
        return AskResponse(answer=ABSTAIN, confidence=0.0, abstained=True)

    answer = data.answer or ABSTAIN
    abstained = ABSTAIN in answer.lower()

    by_id = {h.element_id: h.element for h in hits}
    claims: list[Claim] = []
    for c in data.claims:
        citations: list[Citation] = []
        for cit in c.citations:
            eid = cit.element_id
            el = by_id.get(eid or "")
            if not el:
                continue
            bbox = BBox(**el.bbox) if el.bbox else None
            citations.append(
                Citation(
                    doc_id=el.doc_id,
                    doc_name=el.doc_name,
                    page=el.page,
                    section=el.section,
                    element_id=eid,
                    bbox=bbox,
                    quote=cit.quote,
                )
            )
        if citations:
            claims.append(Claim(text=c.text or "", citations=citations))

    calcs: list[CalculationResult] = []
    for calc in data.calculations:
        try:
            out = evaluate_expression(
                calc.name or "calc",
                calc.formula or "0",
                {k: float(v) for k, v in (calc.inputs or {}).items()},
            )
            calcs.append(
                CalculationResult(
                    name=out.name,
                    formula=out.formula,
                    inputs=out.inputs,
                    result=out.result,
                )
            )
        except CalcError as exc:
            logger.warning("Calc skipped: %s", exc)

    conf = float(data.confidence or 0.5)
    if ABSTAIN in answer.lower():
        abstained = True
        conf = min(conf, 0.3)
    elif not claims:
        abstained = True
        conf = min(conf, 0.3)
    else:
        abstained = False

    return AskResponse(
        answer=answer,
        reasoning_summary=data.reasoning_summary,
        claims=claims,
        calculations=calcs,
        confidence=conf,
        abstained=abstained,
    )
