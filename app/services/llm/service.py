"""Application-level LLM helpers.

These functions operate **only** on the
:class:`LLMProvider <app.services.llm.base.LLMProvider>` interface —
they never import concrete providers. Routers and services should call
into here (or use the provider directly via the ``get_llm`` dependency).
"""

from __future__ import annotations

import neatlogs

from collections.abc import AsyncIterator

from app.services.llm.base import (
    ChatMessage,
    ChatRole,
    LLMProvider,
    LLMResponse,
    StreamChunk,
)

from app.services.llm.factory import (
    get_fallback_models,
    get_llm_provider_for_model,
)
from app.services.llm.base import (
    LLMProviderError,
)


@neatlogs.span(
    kind="CHAIN",
    name="llm.chat",
)
def chat(
    messages: list[ChatMessage],
    provider: LLMProvider,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Run a chat completion with any provider implementation."""
    return provider.chat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


@neatlogs.span(
    kind="CHAIN",
    name="llm.chat",
)
async def achat(
    messages: list[ChatMessage],
    provider: LLMProvider,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Run chat with automatic model fallback."""

    primary_model = (
        model
        or provider.model
    )

    try:
        active_provider = (
            get_llm_provider_for_model(
                primary_model
            )
            if model
            else provider
        )

        return await active_provider.achat(
            messages,
            model=primary_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    except LLMProviderError as primary_error:
        fallback_models = [
            fallback
            for fallback in get_fallback_models()
            if fallback != primary_model
        ]

        if not fallback_models:
            raise

        last_error: Exception = primary_error

        for fallback_model in fallback_models:
            try:
                fallback_provider = (
                    get_llm_provider_for_model(
                        fallback_model
                    )
                )

                return await fallback_provider.achat(
                    messages,
                    model=fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            except LLMProviderError as fallback_error:
                last_error = fallback_error

        raise LLMProviderError(
            (
                "Primary LLM model and all configured "
                "fallback models failed."
            ),
            provider=primary_error.provider,
            model=primary_model,
        ) from last_error


def generate_text(
    prompt: str,
    provider: LLMProvider,
    *,
    model: str | None = None,
    system: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Single-prompt helper with any provider implementation."""
    messages: list[ChatMessage] = []
    if system:
        messages.append(ChatMessage(role=ChatRole.SYSTEM, content=system))
    messages.append(ChatMessage(role=ChatRole.USER, content=prompt))
    return provider.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)


async def agenerate_text(
    prompt: str,
    provider: LLMProvider,
    *,
    model: str | None = None,
    system: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Async single-prompt helper with any provider implementation."""
    messages: list[ChatMessage] = []
    if system:
        messages.append(ChatMessage(role=ChatRole.SYSTEM, content=system))
    messages.append(ChatMessage(role=ChatRole.USER, content=prompt))
    return await provider.achat(messages, model=model, temperature=temperature, max_tokens=max_tokens)


async def astream(
    messages: list[ChatMessage],
    provider: LLMProvider,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[StreamChunk]:
    """Yield text deltas from any provider implementation."""
    async for chunk in provider.astream(
        messages, model=model, temperature=temperature, max_tokens=max_tokens
    ):
        yield chunk
