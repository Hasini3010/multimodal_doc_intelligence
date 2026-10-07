"""Figure/chart VLM extraction via LLM (cached by provider, model, crop hash)."""



from __future__ import annotations



import hashlib

import json

import logging

import re

from pathlib import Path



from agent.llm_client import LLMClient, LLMClientError, get_llm_client

from agent.llm_schemas import FigureOutput

from agent.prompts import FIGURE_EXTRACT_SYSTEM

from app.config import Settings, get_settings



logger = logging.getLogger(__name__)





def crop_sha256(path: Path) -> str:

    data = path.read_bytes()

    return hashlib.sha256(data).hexdigest()





def _cache_key(settings: Settings, crop_sha: str) -> Path:

    client = get_llm_client(settings)

    prov = client.provider_name()

    model = settings.model_role_map().get("vlm", "vlm")

    safe = re.sub(r"[^\w.-]+", "_", model)[:80]

    cache_dir = settings.resolve_path(settings.llm_cache_dir) / "figures"

    cache_dir.mkdir(parents=True, exist_ok=True)

    return cache_dir / f"{prov}_{safe}_{crop_sha}.json"





def _run_vlm_extract(

    crop_path: Path,

    client: LLMClient,

) -> FigureOutput | None:

    image_bytes = crop_path.read_bytes()

    res = client.chat(

        [

            {"role": "system", "content": FIGURE_EXTRACT_SYSTEM},

            {"role": "user", "content": "Extract chart data from this image."},

        ],

        model_role="vlm",

        images=[(image_bytes, "image/png")],

        json_schema=FigureOutput,

    )

    if isinstance(res.parsed, FigureOutput):

        return res.parsed

    return FigureOutput.model_validate_json(res.text)





def _merge_agreed_extractions(a: FigureOutput, b: FigureOutput) -> dict:

    """Keep fields from a; merge numeric table rows that appear in both."""

    base = a.model_dump()

    if not a.uncertain and a.confidence >= 0.75:

        return base

    if a.values_markdown.strip() and a.values_markdown.strip() == b.values_markdown.strip():

        base["uncertain"] = False

        base["confidence"] = max(a.confidence, b.confidence, 0.7)

    else:

        base["uncertain"] = True

        base["confidence"] = min(a.confidence, b.confidence, 0.5)

    return base





def extract_figure_json(

    crop_path: Path,

    *,

    client: LLMClient | None = None,

    settings: Settings | None = None,

) -> dict | None:

    settings = settings or get_settings()

    client = client or get_llm_client(settings)

    if not client.llm_configured():

        logger.info("Skipping VLM figure extract (no LLM API key): %s", crop_path.name)

        return None

    if not crop_path.exists():

        return None



    sha = crop_sha256(crop_path)

    cache_file = _cache_key(settings, sha)

    if cache_file.exists():

        return json.loads(cache_file.read_text(encoding="utf-8"))



    try:

        first = _run_vlm_extract(crop_path, client)

        if first is None:

            return None

        data: dict

        if first.uncertain or first.confidence < 0.75:

            second = _run_vlm_extract(crop_path, client)

            if second:

                data = _merge_agreed_extractions(first, second)

            else:

                data = first.model_dump()

        else:

            data = first.model_dump()

        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return data

    except (LLMClientError, json.JSONDecodeError, OSError) as exc:

        logger.warning("Figure VLM failed for %s: %s", crop_path.name, exc)

        return None





def figure_index_text(vlm: dict | None, fallback: str = "") -> str:

    if not vlm:

        return fallback

    parts = [

        vlm.get("caption") or "",

        vlm.get("chart_type") or "",

        vlm.get("x_axis_label") or "",

        vlm.get("y_axis_label") or "",

        vlm.get("values_markdown") or "",

        " ".join(vlm.get("key_trends") or []),

        json.dumps(vlm.get("data_points") or []),

    ]

    return "\n".join(p for p in parts if p).strip() or fallback

