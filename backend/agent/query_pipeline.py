"""End-to-end /ask pipeline."""



from __future__ import annotations



import logging



from agent.answerer import answer_question

from agent.llm_client import LLMClient, get_llm_client

from agent.planner import plan_question

from agent.verifier import verify_response

from app.config import get_settings

from app.schemas import AskResponse

from indexing.store import load_document_index

from retrieval.hybrid import hybrid_search

from retrieval.rerank import rerank_hits



logger = logging.getLogger(__name__)



ABSTAIN = "not found in the provided documents"





def ask(

    question: str,

    doc_ids: list[str] | None = None,

    client: LLMClient | None = None,

) -> AskResponse:

    settings = get_settings()

    index_dir = settings.resolve_path(settings.index_dir)

    doc_index = load_document_index(index_dir)

    if not doc_index.elements:

        return AskResponse(answer=ABSTAIN, confidence=0.0, abstained=True)



    client = client or get_llm_client()

    subs = plan_question(question, client=client)

    all_hits = []

    seen: set[str] = set()

    for sub in subs:

        raw = hybrid_search(doc_index, sub.text, top_k=20, doc_ids=doc_ids)

        for h in raw:

            if h.element_id not in seen:

                seen.add(h.element_id)

                all_hits.append(h)



    if not all_hits:

        return AskResponse(answer=ABSTAIN, confidence=0.0, abstained=True)



    top = rerank_hits(question, all_hits, top_k=8)

    max_rrf = max((float(h.score) for h in top), default=0.0)

    if max_rrf < 0.01 and not doc_ids:

        return AskResponse(answer=ABSTAIN, confidence=0.15, abstained=True)



    draft = answer_question(question, top, client=client)

    texts = {h.element_id: h.element.text for h in top}

    return verify_response(draft, texts, client=client)

