from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from agent.llm_client import (
    LLMClient,
    LLMClientError,
    LLMRateLimitError,
    LLMUnavailableError,
    extract_first_json_object,
)
from app.config import Settings


class _MiniSchema(BaseModel):
    ok: bool = True


@pytest.fixture
def settings(tmp_path):
    return Settings(
        LLM_PROVIDER="nvidia",
        NVIDIA_API_KEY="test-nvidia-key",
        NVIDIA_MODEL_PRO="model-pro",
        NVIDIA_MODEL_FAST="model-fast",
        NVIDIA_MODEL_LITE="model-lite",
        NVIDIA_MODEL_VLM="model-vlm",
        NVIDIA_RPM=120,
        LLM_CACHE_DIR=tmp_path / "llm_cache",
        LLM_CACHE_ENABLED=True,
        LLM_MAX_RETRIES=2,
        LLM_BACKOFF_BASE_SEC=0.01,
        LLM_BACKOFF_MAX_SEC=0.05,
    )


def _mock_openai_client():
    mock_client = MagicMock()
    mock_models = MagicMock()
    mock_models.data = [
        MagicMock(id="model-pro"),
        MagicMock(id="model-fast"),
        MagicMock(id="model-lite"),
    ]
    mock_client.models.list.return_value = mock_models
    return mock_client


class TestJsonExtract:
    def test_extract_from_prose(self):
        obj = extract_first_json_object('Here: {"a": 1} thanks')
        assert obj["a"] == 1


class TestLLMClientCache:
    def test_cache_hit_skips_api(self, settings):
        client = LLMClient(settings=settings)
        mock_oai = _mock_openai_client()
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
        mock_oai.chat.completions.create.return_value = completion

        with patch("openai.OpenAI", return_value=mock_oai):
            first = client.chat(
                [{"role": "user", "content": "hi"}],
                model_role="fast",
                json_schema=_MiniSchema,
            )
            assert first.cached is False
            assert mock_oai.chat.completions.create.call_count >= 1
            calls_before = mock_oai.chat.completions.create.call_count
            second = client.chat(
                [{"role": "user", "content": "hi"}],
                model_role="fast",
                json_schema=_MiniSchema,
            )
            assert second.cached is True
            assert mock_oai.chat.completions.create.call_count == calls_before


class TestLLMClientRateLimit:
    def test_backoff_on_429(self, settings):
        client = LLMClient(settings=settings)
        mock_oai = _mock_openai_client()
        err = Exception("429 rate limit")
        err.status_code = 429
        ok = MagicMock()
        ok.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
        mock_oai.chat.completions.create.side_effect = [err, ok]

        with patch("openai.OpenAI", return_value=mock_oai):
            with patch("agent.llm_client.time.sleep"):
                res = client.chat(
                    [{"role": "user", "content": "q"}],
                    model_role="fast",
                    json_schema=_MiniSchema,
                )
        assert res.text

    def test_raises_when_all_models_exhausted(self, settings):
        client = LLMClient(settings=settings)
        mock_oai = _mock_openai_client()
        err = Exception("429 too many")
        err.status_code = 429
        mock_oai.chat.completions.create.side_effect = err

        with patch("openai.OpenAI", return_value=mock_oai):
            with patch("agent.llm_client.time.sleep"):
                with pytest.raises(LLMRateLimitError):
                    client.chat([{"role": "user", "content": "q"}], model_role="pro")


class TestLLMClient5xx:
    def test_retries_then_fallback(self, settings):
        client = LLMClient(settings=settings)
        mock_oai = _mock_openai_client()
        err503 = Exception("503 unavailable")
        err503.status_code = 503
        ok = MagicMock()
        ok.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
        mock_oai.chat.completions.create.side_effect = [err503, err503, ok]

        with patch("openai.OpenAI", return_value=mock_oai):
            with patch("agent.llm_client.time.sleep"):
                res = client.chat(
                    [{"role": "user", "content": "q"}],
                    model_role="fast",
                    json_schema=_MiniSchema,
                )
        assert res.parsed is not None
        assert res.model in ("model-fast", "model-pro")


class TestLLMClientJsonRepair:
    def test_repair_invalid_json(self, settings):
        client = LLMClient(settings=settings)
        mock_oai = _mock_openai_client()
        bad = MagicMock()
        bad.choices = [MagicMock(message=MagicMock(content="not json"))]
        good = MagicMock()
        good.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
        mock_oai.chat.completions.create.side_effect = [bad, good]

        with patch("openai.OpenAI", return_value=mock_oai):
            res = client.chat(
                [{"role": "user", "content": "q"}],
                model_role="fast",
                json_schema=_MiniSchema,
            )
        assert res.parsed is not None
        assert res.parsed.ok is True


class TestLLMClientFallback:
    def test_fallback_on_404_model(self, settings):
        client = LLMClient(settings=settings)
        mock_oai = _mock_openai_client()
        err404 = Exception("404 model not found")
        err404.status_code = 404
        ok = MagicMock()
        ok.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]

        def create(**kwargs):
            if kwargs["model"] == "model-pro":
                raise err404
            return ok

        mock_oai.chat.completions.create.side_effect = create

        with patch("openai.OpenAI", return_value=mock_oai):
            res = client.chat(
                [{"role": "user", "content": "q"}],
                model_role="pro",
                json_schema=_MiniSchema,
            )
        assert res.model == "model-fast"


class TestLLMClientCircuitBreaker:
    def test_circuit_opens_after_failures(self, settings):
        import agent.llm_client as lc

        lc._cb_state.clear()
        client = LLMClient(settings=settings)
        mock_oai = _mock_openai_client()
        mock_oai.chat.completions.create.side_effect = RuntimeError("hard fail")

        with patch("openai.OpenAI", return_value=mock_oai):
            with pytest.raises(LLMUnavailableError):
                client.chat([{"role": "user", "content": "x"}], model_role="lite")
        with patch("openai.OpenAI", return_value=mock_oai):
            with pytest.raises(LLMUnavailableError):
                client.chat([{"role": "user", "content": "x"}], model_role="lite")


class TestLLMClientErrors:
    def test_missing_api_key(self, tmp_path):
        s = Settings(
            LLM_PROVIDER="nvidia",
            NVIDIA_API_KEY="",
            LLM_CACHE_DIR=tmp_path / "c",
        )
        client = LLMClient(settings=s)
        with pytest.raises(LLMClientError, match="NVIDIA_API_KEY"):
            client.chat([{"role": "user", "content": "x"}], model_role="fast")
