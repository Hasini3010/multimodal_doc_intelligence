from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.gemini_client import (
    GeminiClient,
    GeminiClientError,
    GeminiRateLimitError,
)
from app.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    cache_dir = tmp_path / "gemini_cache"
    return Settings(
        GEMINI_API_KEY="test-key",
        GEMINI_MODEL_PRO="model-pro",
        GEMINI_MODEL_FAST="model-fast",
        GEMINI_MODEL_LITE="model-lite",
        GEMINI_CACHE_DIR=cache_dir,
        GEMINI_CACHE_ENABLED=True,
        GEMINI_MAX_RETRIES=2,
        GEMINI_BACKOFF_BASE_SEC=0.01,
        GEMINI_BACKOFF_MAX_SEC=0.05,
    )


def _mock_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, candidates=[])


class TestGeminiClientCache:
    def test_cache_hit_skips_api(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _mock_response("api-once")
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff"):
            first = client.generate_text("hello", preferred_tier="fast")
        assert first.text == "api-once"
        assert first.cached is False

        with patch.object(client, "_sleep_backoff"):
            second = client.generate_text("hello", preferred_tier="fast")
        assert second.cached is True
        assert second.text == "api-once"
        assert mock_models.generate_content.call_count == 1

    def test_generate_writes_cache(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()
        mock_models.generate_content.return_value = _mock_response("api-text")
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff"):
            result = client.generate_text("ping", preferred_tier="pro")

        assert result.text == "api-text"
        assert result.model == "model-pro"
        assert result.cached is False
        assert client.call_count == 1

        with patch.object(client, "_sleep_backoff"):
            cached = client.generate_text("ping", preferred_tier="pro")
        assert cached.cached is True
        assert mock_models.generate_content.call_count == 1


class TestGeminiClientRateLimit:
    def test_fallback_after_rate_limit_on_pro(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()

        def side_effect(*, model: str, contents, config):
            if model == "model-pro":
                raise Exception("429 RESOURCE_EXHAUSTED quota")
            return _mock_response(f"ok-{model}")

        mock_models.generate_content.side_effect = side_effect
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff"):
            result = client.generate_text("q", preferred_tier="pro")

        assert result.model == "model-fast"
        assert "ok-model-fast" in result.text

    def test_raises_when_all_models_rate_limited(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("429 rate limit")
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff"):
            with pytest.raises(GeminiRateLimitError):
                client.generate_text("q", preferred_tier="pro")

    def test_backoff_called_on_rate_limit(self, settings: Settings):
        client = GeminiClient(settings=settings)
        attempts = {"n": 0}

        def side_effect(*, model: str, contents, config):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise Exception("429 Too Many Requests")
            return _mock_response("done")

        mock_models = MagicMock()
        mock_models.generate_content.side_effect = side_effect
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff") as sleep_mock:
            result = client.generate_text("q", preferred_tier="fast")

        assert result.text == "done"
        assert sleep_mock.call_count >= 1


class TestGeminiClientModelFallback:
    def test_skips_retries_when_daily_quota_zero(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()
        calls: list[str] = []

        def side_effect(*, model: str, contents, config):
            calls.append(model)
            if model == "model-pro":
                raise Exception(
                    "429 RESOURCE_EXHAUSTED limit: 0, model: gemini-3.1-pro "
                    "Please retry in 16h38m39s."
                )
            return _mock_response(f"ok-{model}")

        mock_models.generate_content.side_effect = side_effect
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff") as sleep_mock:
            result = client.generate_text("q", preferred_tier="pro")

        assert result.model == "model-fast"
        assert calls.count("model-pro") == 1
        assert sleep_mock.call_count == 0

    def test_fallback_on_503_then_lite(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()

        def side_effect(*, model: str, contents, config):
            if model == "model-fast":
                raise Exception(
                    "503 UNAVAILABLE high demand Please try again later."
                )
            return _mock_response(f"ok-{model}")

        mock_models.generate_content.side_effect = side_effect
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff"):
            result = client.generate_text("q", preferred_tier="fast")

        assert result.model == "model-lite"
        assert "ok-model-lite" in result.text

    def test_fallback_on_404_model(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()

        def side_effect(*, model: str, contents, config):
            if model == "model-pro":
                raise Exception("404 NOT_FOUND no longer available")
            return _mock_response(f"ok-{model}")

        mock_models.generate_content.side_effect = side_effect
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff"):
            result = client.generate_text("q", preferred_tier="pro")

        assert result.model == "model-fast"


class TestGeminiClientErrors:
    def test_missing_api_key(self, tmp_path: Path):
        s = Settings(
            GEMINI_API_KEY="",
            GEMINI_CACHE_DIR=tmp_path / "c",
        )
        client = GeminiClient(settings=s)
        with pytest.raises(GeminiClientError, match="GEMINI_API_KEY"):
            client.generate_text("x")

    def test_non_rate_limit_error_propagates(self, settings: Settings):
        client = GeminiClient(settings=settings)
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = ValueError("bad request")
        client._client = MagicMock(models=mock_models)

        with patch.object(client, "_sleep_backoff"):
            with pytest.raises(GeminiClientError, match="bad request"):
                client.generate_text("q", preferred_tier="fast")
