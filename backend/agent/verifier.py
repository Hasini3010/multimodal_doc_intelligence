from __future__ import annotations



import logging

import os



from agent.llm_client import LLMClient, get_llm_client

from agent.llm_schemas import VerifierOutput

from agent.prompts import VERIFIER_SYSTEM

from app.schemas import AskResponse, Claim



logger = logging.getLogger(__name__)





def _quote_in_text(quote: str | None, element_text: str) -> bool:

    if not quote or not quote.strip():

        return True

    q = " ".join(quote.lower().split())

    t = " ".join(element_text.lower().split())

    return q in t or q[:40] in t





def verify_response(

    response: AskResponse,

    element_texts: dict[str, str],

    client: LLMClient | None = None,

) -> AskResponse:

    """Drop unsupported claims; lower confidence if none remain."""

    client = client or get_llm_client()

    kept: list[Claim] = []



    for claim in response.claims:

        valid_citations = []

        for cit in claim.citations:

            eid = cit.element_id or ""

            text = element_texts.get(eid, "")

            if not _quote_in_text(cit.quote, text):

                continue

            if os.getenv("VERIFIER_SKIP_LLM", "").lower() in ("1", "true"):

                valid_citations.append(cit)

                continue

            try:

                prompt = f"Claim: {claim.text}\nEvidence: {text[:1500]}\nQuote: {cit.quote or ''}"

                res = client.chat(

                    [

                        {"role": "system", "content": VERIFIER_SYSTEM},

                        {"role": "user", "content": prompt},

                    ],

                    model_role="fast",

                    json_schema=VerifierOutput,

                )

                verdict = (

                    res.parsed

                    if isinstance(res.parsed, VerifierOutput)

                    else VerifierOutput.model_validate_json(res.text)

                )

                if verdict.supported:

                    valid_citations.append(cit)

            except Exception as exc:

                logger.warning("Verifier LLM skip (%s); keeping citation", exc)

                valid_citations.append(cit)

        if valid_citations:

            kept.append(Claim(text=claim.text, citations=valid_citations))



    conf = response.confidence

    if not kept and not response.abstained:

        return AskResponse(

            answer="not found in the provided documents",

            reasoning_summary=response.reasoning_summary,

            claims=[],

            calculations=response.calculations,

            confidence=0.2,

            abstained=True,

        )



    if kept:

        conf = min(1.0, conf * (len(kept) / max(1, len(response.claims))))

    return AskResponse(

        answer=response.answer,

        reasoning_summary=response.reasoning_summary,

        claims=kept,

        calculations=response.calculations,

        confidence=conf,

        abstained=response.abstained and not kept,

    )

