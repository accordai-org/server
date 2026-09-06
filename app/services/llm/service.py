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
    """Async chat completion with any provider implementation."""
    return await provider.achat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


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
