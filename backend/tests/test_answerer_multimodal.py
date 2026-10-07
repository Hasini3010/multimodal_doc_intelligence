from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.answerer import answer_question, extract_visual_evidence
from agent.llm_client import (
    ChatResult,
    LLMMultimodalRoutingError,
    LLMClient,
    clear_multimodal_unsupported_cache,
    is_model_multimodal_unsupported,
)
from agent.llm_schemas import AnswererOutput, ClaimSchema, CitationSchema, VlmAnswerExtraction
from app.config import Settings
from indexing.store import IndexedElement
from retrieval.hybrid import RetrievalHit


@dataclass
class RecordingLLMClient:
    settings: Settings = field(default_factory=Settings)
    calls: list[dict] = field(default_factory=list)

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": list(messages), **kwargs})
        role = kwargs.get("model_role")
        images = kwargs.get("images")
        schema = kwargs.get("json_schema")
        if images and schema is VlmAnswerExtraction:
            return ChatResult(
                text='{"element_id":"fig1","extracted_values":"| Q | 1 |","units":"%","trend_summary":"up","uncertain":false}',
                model="model-vlm",
                parsed=VlmAnswerExtraction(
                    element_id="fig1",
                    extracted_values="| Q | 1 |",
                    units="%",
                    trend_summary="up",
                    uncertain=False,
                ),
            )
        if schema is AnswererOutput:
            return ChatResult(
                text='{"answer":"ok","claims":[{"text":"c","citations":[{"element_id":"fig1","quote":"1"}]}],"confidence":0.9}',
                model="model-pro",
                parsed=AnswererOutput(
                    answer="ok",
                    claims=[
                        ClaimSchema(
                            text="c",
                            citations=[CitationSchema(element_id="fig1", quote="1")],
                        )
                    ],
                    confidence=0.9,
                ),
            )
        return ChatResult(text="{}", model="model-vlm")


def _hit(element_id: str, crop: Path, etype: str = "figure") -> RetrievalHit:
    el = IndexedElement(
        element_id=element_id,
        doc_id="d1",
        doc_name="doc.pdf",
        page=1,
        section="S",
        type=etype,
        text="caption text",
        bbox={"x0": 0, "y0": 0, "x1": 1, "y1": 1},
        crop_path=str(crop),
    )
    return RetrievalHit(element_id=element_id, score=1.0, element=el, sources={})


class TestAutoRerouteToVLM:
    def test_images_with_pro_role_rerouted_to_vlm(self, tmp_path):
        clear_multimodal_unsupported_cache()
        settings = Settings(
            LLM_PROVIDER="nvidia",
            NVIDIA_API_KEY="k",
            NVIDIA_MODEL_PRO="model-pro",
            NVIDIA_MODEL_FAST="model-fast",
            NVIDIA_MODEL_LITE="model-lite",
            NVIDIA_MODEL_VLM="model-vlm",
            LLM_CACHE_DIR=tmp_path / "cache",
            LLM_CACHE_ENABLED=False,
        )
        client = LLMClient(settings=settings)
        mock_oai = __import__("unittest.mock").mock.MagicMock()
        ok = __import__("unittest.mock").mock.MagicMock()
        ok.choices = [__import__("unittest.mock").mock.MagicMock(message=__import__("unittest.mock").mock.MagicMock(content='{"ok":true}'))]

        def create(**kwargs):
            if kwargs["model"] == "model-pro":
                raise AssertionError("pro must not receive images")
            return ok

        mock_oai.chat.completions.create.side_effect = create
        mock_oai.models.list.return_value = __import__("unittest.mock").mock.MagicMock(data=[])

        with patch("openai.OpenAI", return_value=mock_oai):
            client.chat(
                [{"role": "user", "content": "x"}],
                model_role="pro",
                images=[(b"\x89PNG", "image/png")],
            )
        models_used = [c.kwargs.get("model") for c in mock_oai.chat.completions.create.call_args_list]
        assert "model-pro" not in models_used
        assert "model-vlm" in models_used

    def test_strict_routing_raises(self, tmp_path):
        settings = Settings(
            LLM_PROVIDER="nvidia",
            NVIDIA_API_KEY="k",
            NVIDIA_MODEL_PRO="model-pro",
            NVIDIA_MODEL_VLM="model-vlm",
            LLM_STRICT_MULTIMODAL_ROUTING=True,
            LLM_CACHE_DIR=tmp_path / "cache",
        )
        client = LLMClient(settings=settings)
        with pytest.raises(LLMMultimodalRoutingError):
            client.chat(
                [{"role": "user", "content": "x"}],
                model_role="pro",
                images=[(b"img", "image/png")],
            )

    def test_no_images_no_reroute(self, tmp_path):
        settings = Settings(
            LLM_PROVIDER="nvidia",
            NVIDIA_API_KEY="k",
            NVIDIA_MODEL_PRO="model-pro",
            NVIDIA_MODEL_VLM="model-vlm",
            LLM_CACHE_DIR=tmp_path / "cache",
            LLM_CACHE_ENABLED=False,
        )
        client = LLMClient(settings=settings)
        mock_oai = __import__("unittest.mock").mock.MagicMock()
        ok = __import__("unittest.mock").mock.MagicMock()
        ok.choices = [__import__("unittest.mock").mock.MagicMock(message=__import__("unittest.mock").mock.MagicMock(content="hi"))]
        mock_oai.chat.completions.create.return_value = ok
        mock_oai.models.list.return_value = __import__("unittest.mock").mock.MagicMock(data=[])

        with patch("openai.OpenAI", return_value=mock_oai):
            client.chat([{"role": "user", "content": "x"}], model_role="pro")
        assert mock_oai.chat.completions.create.call_args.kwargs["model"] == "model-pro"

    def test_vlm_role_stays_vlm(self, tmp_path):
        settings = Settings(
            LLM_PROVIDER="nvidia",
            NVIDIA_API_KEY="k",
            NVIDIA_MODEL_VLM="model-vlm",
            NVIDIA_VLM_MODELS="model-vlm,model-vlm-backup",
            LLM_CACHE_DIR=tmp_path / "cache",
            LLM_CACHE_ENABLED=False,
        )
        chain = settings.vlm_fallback_chain()
        assert chain == ["model-vlm", "model-vlm-backup"]


class TestMultimodal400Fallback:
    def test_multimodal_error_skips_model(self, tmp_path):
        clear_multimodal_unsupported_cache()
        settings = Settings(
            LLM_PROVIDER="nvidia",
            NVIDIA_API_KEY="k",
            NVIDIA_MODEL_VLM="bad-vlm",
            NVIDIA_VLM_MODELS="bad-vlm,good-vlm",
            LLM_CACHE_DIR=tmp_path / "cache",
            LLM_CACHE_ENABLED=False,
            LLM_MAX_RETRIES=1,
        )
        client = LLMClient(settings=settings)
        mock_oai = __import__("unittest.mock").mock.MagicMock()
        err = Exception("multimodal processing is not enabled")
        err.status_code = 400
        ok = __import__("unittest.mock").mock.MagicMock()
        ok.choices = [__import__("unittest.mock").mock.MagicMock(message=__import__("unittest.mock").mock.MagicMock(content='{"ok":true}'))]

        def create(**kwargs):
            if kwargs["model"] == "bad-vlm":
                raise err
            return ok

        mock_oai.chat.completions.create.side_effect = create
        mock_oai.models.list.return_value = __import__("unittest.mock").mock.MagicMock(data=[])

        with patch("openai.OpenAI", return_value=mock_oai):
            res = client.chat(
                [{"role": "user", "content": "x"}],
                model_role="vlm",
                images=[(b"i", "image/png")],
            )
        assert res.model == "good-vlm"
        assert is_model_multimodal_unsupported("bad-vlm")


class TestTwoStageAnswerer:
    def test_vlm_called_once_per_image(self, tmp_path):
        crop1 = tmp_path / "a.png"
        crop2 = tmp_path / "b.png"
        crop1.write_bytes(b"png1")
        crop2.write_bytes(b"png2")
        client = RecordingLLMClient()
        hits = [_hit("fig1", crop1), _hit("fig2", crop2)]
        extract_visual_evidence("What is Q4?", hits, client=client)
        vlm_calls = [c for c in client.calls if c.get("images")]
        assert len(vlm_calls) == 2
        for call in vlm_calls:
            assert len(call["images"]) == 1

    def test_cache_hit_avoids_second_vlm_call(self, tmp_path):
        settings = Settings(
            LLM_PROVIDER="nvidia",
            NVIDIA_API_KEY="k",
            NVIDIA_MODEL_VLM="model-vlm",
            LLM_CACHE_DIR=tmp_path / "cache",
            LLM_CACHE_ENABLED=True,
        )
        client = LLMClient(settings=settings)
        mock_oai = __import__("unittest.mock").mock.MagicMock()
        ok = __import__("unittest.mock").mock.MagicMock()
        ok.choices = [
            __import__("unittest.mock").mock.MagicMock(
                message=__import__("unittest.mock").mock.MagicMock(
                    content='{"element_id":"f","extracted_values":"1","uncertain":false}'
                )
            )
        ]
        mock_oai.chat.completions.create.return_value = ok
        mock_oai.models.list.return_value = __import__("unittest.mock").mock.MagicMock(data=[])

        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q"},
        ]
        imgs = [(b"same", "image/png")]
        with patch("openai.OpenAI", return_value=mock_oai):
            client.chat(msgs, model_role="vlm", images=imgs, json_schema=VlmAnswerExtraction)
            n = mock_oai.chat.completions.create.call_count
            client.chat(msgs, model_role="vlm", images=imgs, json_schema=VlmAnswerExtraction)
            assert mock_oai.chat.completions.create.call_count == n

    def test_final_pro_call_has_no_images(self, tmp_path):
        crop = tmp_path / "a.png"
        crop.write_bytes(b"png1")
        client = RecordingLLMClient()
        hits = [
            _hit("fig1", crop),
            RetrievalHit(
                element_id="t1",
                score=1.0,
                element=IndexedElement(
                    element_id="t1",
                    doc_id="d1",
                    doc_name="doc.pdf",
                    page=2,
                    section="S",
                    type="text",
                    text="Production was high in Q4.",
                    bbox={"x0": 0, "y0": 0, "x1": 1, "y1": 1},
                    crop_path=None,
                ),
                sources={},
            ),
        ]
        answer_question("What is Q4?", hits, client=client)
        pro_calls = [c for c in client.calls if c.get("model_role") == "pro"]
        assert len(pro_calls) == 1
        assert pro_calls[0].get("images") is None
