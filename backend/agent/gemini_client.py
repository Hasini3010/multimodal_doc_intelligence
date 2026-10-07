"""Backward-compatible re-exports; implementation lives in llm_client.py."""

from agent.llm_client import (
    ChatResult,
    GeminiClientError,
    GeminiRateLimitError,
    GenerateResult,
    LLMClient,
    LLMClientError,
    LLMRateLimitError,
    LLMUnavailableError,
    get_gemini_client,
    get_llm_client,
)

GeminiClient = LLMClient

__all__ = [
    "ChatResult",
    "GeminiClient",
    "GeminiClientError",
    "GeminiRateLimitError",
    "GenerateResult",
    "LLMClient",
    "LLMClientError",
    "LLMRateLimitError",
    "LLMUnavailableError",
    "get_gemini_client",
    "get_llm_client",
]
