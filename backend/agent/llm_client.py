"""Unified LLM/VLM client: NVIDIA NIM (primary) and optional Gemini, with caching and fallbacks."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import random
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_RATE_LIMIT_RE = re.compile(r"429|rate.?limit|too many", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)

IMAGE_MAX_SIDE = 1568
IMAGE_JPEG_QUALITY = 85


class LLMClientError(Exception):
    """Non-recoverable LLM client error."""


class LLMRateLimitError(LLMClientError):
    """Rate limit / quota exhausted after retries and fallbacks."""


class LLMUnavailableError(LLMClientError):
    """All models / providers failed; API should return 503."""


class LLMMultimodalRoutingError(LLMClientError):
    """Images sent to a text-only model while strict multimodal routing is enabled."""


@dataclass
class ChatResult:
    text: str
    model: str
    cached: bool = False
    parsed: Any = None


@dataclass
class GenerateResult:
    """Backward-compatible alias used by ingestion helpers."""

    text: str
    model: str
    cached: bool = False
    raw: Any = None


# --- Token bucket (per model, thread-safe) ---

_buckets_lock = threading.Lock()
_buckets: dict[str, tuple[float, float]] = {}  # model -> (tokens, last_ts)


def _token_bucket_wait(model: str, rpm: int) -> None:
    if rpm <= 0:
        return
    rate = rpm / 60.0
    with _buckets_lock:
        tokens, last = _buckets.get(model, (float(rpm), time.monotonic()))
        now = time.monotonic()
        tokens = min(float(rpm), tokens + (now - last) * rate)
        if tokens < 1.0:
            need = (1.0 - tokens) / rate
            time.sleep(need)
            now = time.monotonic()
            tokens = min(float(rpm), tokens + (now - last) * rate)
        tokens -= 1.0
        _buckets[model] = (tokens, now)


# --- Circuit breaker (per model) ---

_cb_lock = threading.Lock()
_cb_state: dict[str, tuple[int, float | None]] = {}  # failures, open_until
CB_FAILURE_THRESHOLD = 5
CB_OPEN_SEC = 120.0

_mm_lock = threading.Lock()
_multimodal_disabled_models: set[str] = set()


def _circuit_allow(model: str) -> bool:
    with _cb_lock:
        failures, open_until = _cb_state.get(model, (0, None))
        if open_until and time.monotonic() < open_until:
            return False
        if open_until and time.monotonic() >= open_until:
            _cb_state[model] = (0, None)
        return True


def _circuit_success(model: str) -> None:
    with _cb_lock:
        _cb_state[model] = (0, None)


def _circuit_failure(model: str) -> None:
    with _cb_lock:
        failures, _ = _cb_state.get(model, (0, None))
        failures += 1
        open_until = None
        if failures >= CB_FAILURE_THRESHOLD:
            open_until = time.monotonic() + CB_OPEN_SEC
            logger.warning("Circuit open for model %s (%ss)", model, CB_OPEN_SEC)
        _cb_state[model] = (failures, open_until)


# --- Image prep (cached by raw content hash) ---

_image_cache_lock = threading.Lock()
_image_cache: dict[str, tuple[str, str]] = {}  # sha -> (mime, b64)


def prepare_image_bytes(data: bytes, *, mime_hint: str = "image/png") -> tuple[str, str]:
    """Downscale/compress; return (mime_type, base64) for data URL."""
    sha = hashlib.sha256(data).hexdigest()
    with _image_cache_lock:
        if sha in _image_cache:
            return _image_cache[sha]

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, IMAGE_MAX_SIDE / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
        out_bytes = buf.getvalue()
        mime = "image/jpeg"
    except Exception as exc:
        logger.debug("Image prep fallback (%s)", exc)
        out_bytes = data
        mime = mime_hint if mime_hint.startswith("image/") else "image/png"

    b64 = base64.standard_b64encode(out_bytes).decode("ascii")
    with _image_cache_lock:
        _image_cache[sha] = (mime, b64)
    return mime, b64


def image_data_url(data: bytes, mime_hint: str = "image/png") -> str:
    mime, b64 = prepare_image_bytes(data, mime_hint=mime_hint)
    return f"data:{mime};base64,{b64}"


def extract_first_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    match = _JSON_OBJECT_RE.search(text)
    if not match:
        raise json.JSONDecodeError("No JSON object in response", text, 0)
    return json.loads(match.group(0))


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def list_models(self) -> set[str]:
        ...

    @abstractmethod
    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None,
        json_schema: dict[str, Any] | None,
    ) -> str:
        ...


class NvidiaProvider(LLMProvider):
    name = "nvidia"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None
        self._models: set[str] | None = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = self.settings.nvidia_api_key.strip()
        if not key:
            raise LLMClientError(
                "NVIDIA_API_KEY is not set. Add it to .env (see .env.example)."
            )
        from openai import OpenAI

        self._client = OpenAI(
            api_key=key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        return self._client

    def list_models(self) -> set[str]:
        if self._models is not None:
            return self._models
        try:
            client = self._ensure_client()
            resp = client.models.list()
            ids = {m.id for m in resp.data}
            self._models = ids
            return ids
        except Exception as exc:
            logger.warning("NVIDIA models.list failed: %s", exc)
            self._models = set()
            return self._models

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None,
        json_schema: dict[str, Any] | None,
    ) -> str:
        client = self._ensure_client()
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": json_schema,
                    "strict": False,
                },
            }
        try:
            resp = client.chat.completions.create(**kwargs)
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            if json_schema and _is_bad_request_json_schema(exc):
                kwargs.pop("response_format", None)
                resp = client.chat.completions.create(**kwargs)
                return (resp.choices[0].message.content or "").strip()
            raise


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None
        self._models: set[str] | None = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = self.settings.gemini_api_key.strip()
        if not key:
            raise LLMClientError("GEMINI_API_KEY is not set.")
        from google import genai

        self._client = genai.Client(api_key=key)
        return self._client

    def list_models(self) -> set[str]:
        if self._models is not None:
            return self._models
        try:
            client = self._ensure_client()
            names: set[str] = set()
            for m in client.models.list():
                name = getattr(m, "name", "") or ""
                if name.startswith("models/"):
                    name = name[7:]
                if name:
                    names.add(name)
            self._models = names
            return names
        except Exception as exc:
            logger.warning("Gemini models.list failed: %s", exc)
            self._models = set()
            return self._models

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None,
        json_schema: dict[str, Any] | None,
    ) -> str:
        from google.genai import types

        client = self._ensure_client()
        system = ""
        contents: list[Any] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                system += (content if isinstance(content, str) else "") + "\n"
                continue
            if isinstance(content, str):
                contents.append(content)
            elif isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        contents.append(block.get("text", ""))
                    elif block.get("type") == "image_url":
                        url = block.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            header, b64 = url.split(",", 1)
                            mime = header.split(";")[0].replace("data:", "")
                            contents.append(
                                types.Part.from_bytes(
                                    data=base64.standard_b64decode(b64),
                                    mime_type=mime,
                                )
                            )
        config_dict: dict[str, Any] = {}
        if json_schema:
            config_dict["response_mime_type"] = "application/json"
        if temperature is not None:
            config_dict["temperature"] = temperature
        config = types.GenerateContentConfig(**config_dict)
        if system.strip():
            config.system_instruction = system.strip()
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        text = getattr(response, "text", None) or ""
        if not text:
            for cand in getattr(response, "candidates", None) or []:
                content = getattr(cand, "content", None)
                for p in getattr(content, "parts", None) or []:
                    if getattr(p, "text", None):
                        text += p.text
        return text.strip()


def _is_bad_request_json_schema(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "response_format" in msg or "json_schema" in msg or "400" in msg


def _is_rate_limit(exc: BaseException) -> bool:
    if _RATE_LIMIT_RE.search(str(exc)):
        return True
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code == 429


def _is_transient(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if any(x in msg for x in ("503", "502", "500", "timeout", "unavailable")):
        return True
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code in (500, 502, 503)


def _is_bad_request(exc: BaseException) -> bool:
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code == 400:
        return True
    msg = str(exc).lower()
    return "error code: 400" in msg or "'code': 400" in msg


def _is_multimodal_disabled(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "multimodal" in msg
        or "enable-multimodal" in msg
        or ("image" in msg and ("not enabled" in msg or "not supported" in msg))
    )


def mark_model_multimodal_unsupported(model: str) -> None:
    with _mm_lock:
        _multimodal_disabled_models.add(model)


def is_model_multimodal_unsupported(model: str) -> bool:
    with _mm_lock:
        return model in _multimodal_disabled_models


def clear_multimodal_unsupported_cache() -> None:
    with _mm_lock:
        _multimodal_disabled_models.clear()


def _is_model_missing(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "404" in msg and "model" in msg:
        return True
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code == 404


def _retry_after_sec(exc: BaseException) -> float | None:
    headers = getattr(exc, "headers", None) or getattr(exc, "response", None)
    if headers and hasattr(headers, "get"):
        ra = headers.get("Retry-After") or headers.get("retry-after")
        if ra:
            try:
                return float(ra)
            except ValueError:
                pass
    match = re.search(r"retry[- ]after[:\s]+(\d+)", str(exc), re.I)
    if match:
        return float(match.group(1))
    return None


def _sleep_backoff(attempt: int, settings: Settings, retry_after: float | None) -> None:
    if retry_after is not None:
        delay = retry_after + random.uniform(0, 0.5)
    else:
        delays = [2, 4, 8, 16]
        base = delays[min(attempt, len(delays) - 1)]
        delay = base * (0.85 + random.random() * 0.3)
    cap = settings.llm_backoff_max_sec
    time.sleep(min(cap, delay))


def _pydantic_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()


@dataclass
class LLMClient:
    settings: Settings
    _provider: LLMProvider | None = field(default=None, repr=False)
    _call_count: int = field(default=0, repr=False)
    _models_validated: bool = field(default=False, repr=False)

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset_call_count(self) -> None:
        self._call_count = 0

    def provider_name(self) -> str:
        return self.settings.llm_provider.lower()

    def _select_provider(self) -> LLMProvider:
        if self._provider is not None:
            return self._provider
        p = self.settings.llm_provider.lower().strip()
        if p == "gemini":
            self._provider = GeminiProvider(self.settings)
        else:
            self._provider = NvidiaProvider(self.settings)
        return self._provider

    def llm_configured(self) -> bool:
        p = self.settings.llm_provider.lower().strip()
        if p == "gemini":
            return bool(self.settings.gemini_api_key.strip())
        if bool(self.settings.nvidia_api_key.strip()):
            return True
        if bool(self.settings.gemini_api_key.strip()):
            return True
        return False

    def validate_models_on_startup(self) -> dict[str, str]:
        """Fetch model list once; warn on missing configured IDs; return role map."""
        role_map = self.settings.model_role_map()
        provider = self._select_provider()
        if not self.llm_configured():
            logger.warning("No LLM API key configured")
            return role_map
        available = provider.list_models()
        if available:
            for role, mid in role_map.items():
                if mid and mid not in available:
                    logger.warning(
                        "Configured model %s (%s) not in provider catalog", role, mid
                    )
        table = " | ".join(f"{r}={m}" for r, m in sorted(role_map.items()))
        logger.info(
            "LLM provider=%s roles: %s",
            provider.name,
            table,
        )
        print(f"[LLM] provider={provider.name} {table}")
        self._models_validated = True
        return role_map

    def role_fallback_chain(self, model_role: str) -> list[str]:
        return self.settings.role_fallback_chain(model_role)

    def vlm_model_ids(self) -> set[str]:
        return set(self.settings.vlm_fallback_chain())

    def is_vlm_capable_model(self, model: str) -> bool:
        if self.provider_name() == "gemini":
            return True
        return model in self.vlm_model_ids()

    def _cache_path(self, key_hash: str) -> Path:
        cache_dir = self.settings.resolve_path(self.settings.llm_cache_dir)
        prov = self.provider_name()
        d = cache_dir / prov
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{key_hash}.json"

    def _read_cache(self, key_hash: str) -> ChatResult | None:
        if not self.settings.llm_cache_enabled:
            return None
        path = self._cache_path(key_hash)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ChatResult(
                text=data["text"],
                model=data["model"],
                cached=True,
                parsed=data.get("parsed"),
            )
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Invalid LLM cache %s: %s", path, exc)
            return None

    def _write_cache(
        self, key_hash: str, model: str, text: str, parsed: Any = None
    ) -> None:
        if not self.settings.llm_cache_enabled:
            return
        path = self._cache_path(key_hash)
        payload = {
            "provider": self.provider_name(),
            "model": model,
            "text": text,
            "parsed": parsed,
            "ts": time.time(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _cache_key(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any] | None,
        temperature: float | None,
    ) -> str:
        payload = {
            "provider": self.provider_name(),
            "model": model,
            "messages": messages,
            "json_schema": json_schema,
            "temperature": temperature,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def _build_openai_messages(
        self,
        messages: Sequence[dict[str, Any]],
        images: list[tuple[bytes, str]] | None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [dict(m) for m in messages]
        if images:
            blocks: list[dict[str, Any]] = []
            for msg in reversed(out):
                if msg.get("role") == "user":
                    existing = msg.get("content")
                    if isinstance(existing, str):
                        blocks.append({"type": "text", "text": existing})
                    elif isinstance(existing, list):
                        blocks.extend(existing)
                    for img_bytes, mime in images:
                        url = image_data_url(img_bytes, mime_hint=mime)
                        blocks.append({"type": "image_url", "image_url": {"url": url}})
                    msg["content"] = blocks
                    break
            else:
                blocks = [{"type": "text", "text": ""}]
                for img_bytes, mime in images:
                    url = image_data_url(img_bytes, mime_hint=mime)
                    blocks.append({"type": "image_url", "image_url": {"url": url}})
                out.append({"role": "user", "content": blocks})
        return out

    def _resolve_chat_chain(
        self, model_role: str, images: list[tuple[bytes, str]] | None
    ) -> tuple[str, list[str]]:
        has_images = bool(images)
        role = model_role
        if has_images:
            if role != "vlm" and not self.is_vlm_capable_model(
                self.settings.model_role_map().get(role, "")
            ):
                if self.settings.llm_strict_multimodal_routing:
                    raise LLMMultimodalRoutingError(
                        f"model_role={role!r} cannot accept images; use model_role='vlm' "
                        f"or enable auto-reroute (LLM_STRICT_MULTIMODAL_ROUTING=false)."
                    )
                logger.warning(
                    "chat() received images with model_role=%s; rerouting to VLM chain",
                    role,
                )
                role = "vlm"
            chain = self.settings.vlm_fallback_chain()
        else:
            chain = self.role_fallback_chain(role)
        return role, chain

    def chat(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        model_role: str = "fast",
        images: list[tuple[bytes, str]] | None = None,
        json_schema: type[BaseModel] | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        schema_dict = _pydantic_to_json_schema(json_schema) if json_schema else None
        built = self._build_openai_messages(list(messages), images)
        _, chain = self._resolve_chat_chain(model_role, images)
        if not chain:
            raise LLMClientError(f"Empty fallback chain for role {model_role}")

        last_error: BaseException | None = None
        provider = self._select_provider()
        has_images = bool(images)

        for model in chain:
            if has_images and is_model_multimodal_unsupported(model):
                logger.debug("Skipping model %s (multimodal disabled)", model)
                continue
            if not _circuit_allow(model):
                logger.debug("Skipping circuit-open model %s", model)
                continue

            key_hash = self._cache_key(
                model=model,
                messages=built,
                json_schema=schema_dict,
                temperature=temperature,
            )
            cached = self._read_cache(key_hash)
            if cached is not None:
                if json_schema and cached.parsed is None and cached.text:
                    try:
                        obj = extract_first_json_object(cached.text)
                        cached.parsed = json_schema.model_validate(obj)
                    except (json.JSONDecodeError, ValidationError):
                        pass
                return cached

            max_attempts = max(1, self.settings.llm_max_retries)
            for attempt in range(max_attempts):
                try:
                    _token_bucket_wait(model, self.settings.nvidia_rpm)
                    self._call_count += 1
                    text = provider.complete(
                        model=model,
                        messages=built,
                        temperature=temperature,
                        json_schema=schema_dict,
                    )
                    parsed_obj = None
                    if json_schema:
                        try:
                            obj = extract_first_json_object(text)
                            parsed_obj = json_schema.model_validate(obj)
                        except (json.JSONDecodeError, ValidationError) as val_exc:
                            repair_msg = (
                                f"Fix this to valid JSON matching schema "
                                f"{json_schema.__name__}:\n{text[:4000]}"
                            )
                            repair_messages = built + [
                                {"role": "user", "content": repair_msg}
                            ]
                            self._call_count += 1
                            text = provider.complete(
                                model=model,
                                messages=repair_messages,
                                temperature=0.0,
                                json_schema=schema_dict,
                            )
                            obj = extract_first_json_object(text)
                            parsed_obj = json_schema.model_validate(obj)
                            if val_exc:
                                pass
                    _circuit_success(model)
                    self._write_cache(
                        key_hash,
                        model,
                        text,
                        parsed=parsed_obj.model_dump() if parsed_obj else None,
                    )
                    return ChatResult(
                        text=text,
                        model=model,
                        cached=False,
                        parsed=parsed_obj,
                    )
                except Exception as exc:
                    last_error = exc
                    if _is_rate_limit(exc):
                        ra = _retry_after_sec(exc)
                        logger.warning(
                            "LLM rate limit model=%s attempt=%s: %s",
                            model,
                            attempt,
                            exc,
                        )
                        if attempt + 1 < max_attempts:
                            _sleep_backoff(attempt, self.settings, ra)
                            continue
                        break
                    if _is_transient(exc):
                        logger.warning(
                            "LLM transient model=%s attempt=%s: %s",
                            model,
                            attempt,
                            exc,
                        )
                        if attempt + 1 < max_attempts:
                            _sleep_backoff(attempt, self.settings, None)
                            continue
                        break
                    if _is_model_missing(exc):
                        logger.warning("Model missing %s: %s", model, exc)
                        _circuit_failure(model)
                        break
                    if _is_bad_request(exc):
                        if has_images and _is_multimodal_disabled(exc):
                            mark_model_multimodal_unsupported(model)
                            logger.warning(
                                "Model %s rejected multimodal input: %s",
                                model,
                                exc,
                            )
                        else:
                            logger.warning(
                                "LLM bad request model=%s (no retry): %s", model, exc
                            )
                        _circuit_failure(model)
                        break
                    _circuit_failure(model)
                    logger.warning("LLM error model=%s: %s", model, exc)
                    break

            _circuit_failure(model)

        if last_error and _is_rate_limit(last_error):
            raise LLMRateLimitError(f"All models rate limited. Last error: {last_error}")
        detail = str(last_error) if last_error else "no models in chain"
        raise LLMUnavailableError(f"All models exhausted. Last error: {detail}")


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    return LLMClient(settings=settings or get_settings())


_client_singleton: LLMClient | None = None
_singleton_lock = threading.Lock()


def get_llm_client_singleton() -> LLMClient:
    global _client_singleton
    with _singleton_lock:
        if _client_singleton is None:
            _client_singleton = get_llm_client()
        return _client_singleton


# --- Backward-compatible generate_text API ---

def _contents_to_messages(
    contents: str | Sequence[Any],
    system_instruction: str | None,
) -> tuple[list[dict[str, Any]], list[tuple[bytes, str]] | None]:
    images: list[tuple[bytes, str]] = []
    text_parts: list[str] = []
    if isinstance(contents, str):
        text_parts.append(contents)
    else:
        for part in contents:
            if isinstance(part, str):
                text_parts.append(part)
                continue
            if isinstance(part, dict) and part.get("type") == "image_url":
                continue
            if hasattr(part, "inline_data") and part.inline_data:
                blob = part.inline_data
                data = getattr(blob, "data", None) or b""
                mime = getattr(blob, "mime_type", None) or "image/png"
                images.append((bytes(data), mime))
                continue
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
                continue
            text_parts.append(str(part))

    messages: list[dict[str, Any]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": "\n".join(text_parts)})
    return messages, images or None


def _generate_text_impl(
    self: LLMClient,
    contents: str | Sequence[Any],
    *,
    preferred_tier: str = "pro",
    system_instruction: str | None = None,
    json_mode: bool = False,
    temperature: float | None = None,
    pydantic_model: type[BaseModel] | None = None,
) -> GenerateResult:
    role_map = {"pro": "pro", "fast": "fast", "lite": "lite", "vlm": "vlm"}
    model_role = role_map.get(preferred_tier, preferred_tier)
    messages, images = _contents_to_messages(contents, system_instruction)
    schema = pydantic_model if pydantic_model else None
    res = self.chat(
        messages,
        model_role=model_role,
        images=images,
        json_schema=schema if (json_mode or schema) else None,
        temperature=temperature,
    )
    return GenerateResult(text=res.text, model=res.model, cached=res.cached)


LLMClient.generate_text = _generate_text_impl  # type: ignore[method-assign]

GeminiClientError = LLMClientError
GeminiRateLimitError = LLMRateLimitError


def get_gemini_client(settings: Settings | None = None) -> LLMClient:
    return get_llm_client(settings)
