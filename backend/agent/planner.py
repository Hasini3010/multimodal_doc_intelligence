from __future__ import annotations



import logging

from dataclasses import dataclass



from agent.llm_client import LLMClient, LLMRateLimitError, LLMUnavailableError, get_llm_client

from agent.llm_schemas import PlannerOutput

from agent.prompts import PLANNER_SYSTEM



logger = logging.getLogger(__name__)





@dataclass

class SubQuestion:

    text: str

    modality: str = "any"

    needs_math: bool = False





def plan_question(question: str, client: LLMClient | None = None) -> list[SubQuestion]:

    client = client or get_llm_client()

    try:

        res = client.chat(

            [

                {"role": "system", "content": PLANNER_SYSTEM},

                {"role": "user", "content": question},

            ],

            model_role="fast",

            json_schema=PlannerOutput,

        )

        data = res.parsed if isinstance(res.parsed, PlannerOutput) else PlannerOutput.model_validate_json(

            res.text

        )

        out = [

            SubQuestion(

                text=s.text or question,

                modality=s.modality or "any",

                needs_math=bool(s.needs_math),

            )

            for s in data.sub_questions

            if s.text

        ]

        if out:

            return out

    except (LLMUnavailableError, LLMRateLimitError):
        raise
    except Exception as exc:
        logger.warning("Planner fallback (%s)", exc)
    return [SubQuestion(text=question, modality="any", needs_math=False)]

