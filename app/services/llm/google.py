"""Google LLM provider (default model ``gemini-3.8-flash`` via ``google-genai``).

Wraps the official ``google-genai`` SDK (``genai.Client``) behind the
vendor-neutral :class:`LLMProvider <app.services.llm.base.LLMProvider>`
interface. All credentials and model selection come from the caller —
in production, resolved from environment variables by
``app.services.llm.factory``.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterator

from app.services.observability.neatlogs import wrap_client

from app.services.llm.base import (
    ChatMessage,
    ChatRole,
    LLMConfigError,
    LLMError,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMUsage,
    StreamChunk,
)

DEFAULT_MODEL = "gemini-3.8-flash"
PROVIDER_NAME = "google"


def _contents_and_system(messages: list[ChatMessage]) -> tuple[list, str | None]:
    """Split vendor-neutral messages into genai ``contents`` + system instruction."""
    from google.genai import types

    contents: list = []
    system_parts: list[str] = []
    for msg in messages:
        if msg.role == ChatRole.SYSTEM:
            system_parts.append(msg.content)
        elif msg.role == ChatRole.ASSISTANT:
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=msg.content)],
                )
            )
        else:  # USER (and anything else) -> user turn
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.content)],
                )
            )
    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return contents, system_instruction


def _config(
    system_instruction: str | None,
    temperature: float | None,
    max_tokens: int | None,
):  # type: ignore[no-untyped-def]
    from google.genai import types

    kwargs: dict = {}
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_output_tokens"] = max_tokens
    return types.GenerateContentConfig(**kwargs) if kwargs else None


def _to_response(result: object, model: str, latency_ms: int) -> LLMResponse:
    text = (getattr(result, "text", None) or "").strip()
    finish: str | None = None
    try:
        candidates = getattr(result, "candidates", None) or []
        if candidates:
            finish = getattr(candidates[0], "finish_reason", None)
            if finish is not None:
                finish = str(finish).split(".")[-1].lower()
    except Exception:
        finish = None
    usage = None
    raw_usage = getattr(result, "usage_metadata", None)
    if raw_usage is not None:
        prompt_tokens = getattr(raw_usage, "prompt_token_count", None)
        completion_tokens = getattr(raw_usage, "candidates_token_count", None)
        total_tokens = getattr(raw_usage, "total_token_count", None)
        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )
    return LLMResponse(
        content=text,
        model=model,
        provider=PROVIDER_NAME,
        finish_reason=finish,
        usage=usage,
    )


class GoogleProvider(LLMProvider):
    """LLM provider backed by Google's Gemini Developer API via ``google-genai``."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        if not api_key:
            raise LLMConfigError(
                "Google API key is missing. Set GOOGLE_API_KEY "
                "(or LLM_API_KEY) in the environment."
            )
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def model(self) -> str:
        return self._model

    def _client(self):
        from google import genai
    
        client = genai.Client(api_key=self._api_key)
    
        return wrap_client(
            client,
            provider=PROVIDER_NAME,
            model=self._model,
        )

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if not messages:
            raise ValueError("messages must not be empty")
        contents, system_instruction = _contents_and_system(messages)
        config = _config(
            system_instruction,
            temperature if temperature is not None else self._temperature,
            max_tokens if max_tokens is not None else self._max_tokens,
        )
        started = time.perf_counter()
        try:
            if config is None:
                result = self._client().models.generate_content(
                    model=model or self._model, contents=contents
                )
            else:
                result = self._client().models.generate_content(
                    model=model or self._model, contents=contents, config=config
                )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"Google chat completion failed: {exc}",
                provider=PROVIDER_NAME,
                model=model or self._model,
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        return _to_response(result, self._model, latency_ms)

    async def achat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if not messages:
            raise ValueError("messages must not be empty")
        contents, system_instruction = _contents_and_system(messages)
        config = _config(
            system_instruction,
            temperature if temperature is not None else self._temperature,
            max_tokens if max_tokens is not None else self._max_tokens,
        )
        started = time.perf_counter()
        try:
            client = self._client()
            if config is None:
                result = await client.aio.models.generate_content(
                    model=model or self._model, contents=contents
                )
            else:
                result = await client.aio.models.generate_content(
                    model=model or self._model, contents=contents, config=config
                )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"Google chat completion failed: {exc}",
                provider=PROVIDER_NAME,
                model=model or self._model,
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        return _to_response(result, self._model, latency_ms)

    def _stream_kwargs(
        self,
        messages: list[ChatMessage],
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict:
        contents, system_instruction = _contents_and_system(messages)
        config = _config(
            system_instruction,
            temperature if temperature is not None else self._temperature,
            max_tokens if max_tokens is not None else self._max_tokens,
        )
        kwargs: dict = {"model": model or self._model, "contents": contents}
        if config is not None:
            kwargs["config"] = config
        return kwargs

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[StreamChunk]:
        if not messages:
            raise ValueError("messages must not be empty")
        try:
            chunks = self._client().models.generate_content_stream(
                **self._stream_kwargs(messages, model, temperature, max_tokens)
            )
            for chunk in chunks:
                delta = getattr(chunk, "text", None) or ""
                if delta:
                    yield StreamChunk(
                        delta=delta, provider=PROVIDER_NAME, model=model or self._model
                    )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"Google stream failed: {exc}",
                provider=PROVIDER_NAME,
                model=model or self._model,
            ) from exc

    async def astream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if not messages:
            raise ValueError("messages must not be empty")
        try:
            stream = await self._client().aio.models.generate_content_stream(
                **self._stream_kwargs(messages, model, temperature, max_tokens)
            )
            async for chunk in stream:
                delta = getattr(chunk, "text", None) or ""
                if delta:
                    yield StreamChunk(
                        delta=delta, provider=PROVIDER_NAME, model=model or self._model
                    )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"Google stream failed: {exc}",
                provider=PROVIDER_NAME,
                model=model or self._model,
            ) from exc
