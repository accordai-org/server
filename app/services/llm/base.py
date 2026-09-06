"""Vendor-neutral LLM provider interface.

Everything outside ``app.services.llm`` must program against the types
defined here (:class:`ChatMessage`, :class:`LLMResponse`,
:class:`LLMProvider`) and obtain instances via
``app.services.llm.factory`` — never by importing a concrete provider
module (``tensormux``, ``google``) directly.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from enum import Enum

from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    """Chat message roles. Kept to the common subset every provider supports."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """One chat turn. Vendor-neutral; providers map it to their own format."""

    role: ChatRole = Field(description="Message role.")
    content: str = Field(min_length=1, description="Message text content.")


class LLMUsage(BaseModel):
    """Token/latency accounting. All fields optional — providers fill what they can."""

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)


class LLMResponse(BaseModel):
    """Vendor-neutral completion result."""

    content: str = Field(description="Generated text.")
    model: str = Field(description="Model that produced the output.")
    provider: str = Field(description="Provider name, e.g. 'tensormux', 'google'.")
    finish_reason: str | None = Field(default=None)
    usage: LLMUsage | None = Field(default=None)


class StreamChunk(BaseModel):
    """One streamed delta. Providers yield these in order; concatenated = full text."""

    delta: str = Field(description="Incremental text for this chunk.")
    provider: str = Field(description="Provider name, e.g. 'tensormux', 'google'.")
    model: str = Field(description="Model producing the stream.")


class LLMError(Exception):
    """Base class for all LLM errors."""


class LLMConfigError(LLMError):
    """Raised when a provider is misconfigured (missing key, bad URL, ...)."""


class LLMProviderError(LLMError):
    """Raised when the upstream provider call fails."""

    def __init__(self, message: str, *, provider: str = "", model: str = "") -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model


class LLMProvider(ABC):
    """Abstract LLM provider. Implementations wrap one vendor SDK/API."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. ``'tensormux'``. Used for routing/logging."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Default model identifier used when the caller does not override."""

    # ------------------------------------------------------------------
    # Core API — every provider must implement chat (+ async variant).
    # ------------------------------------------------------------------
    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Run a multi-turn chat completion (blocking)."""

    async def achat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Async chat completion. Defaults to running :meth:`chat` in a thread."""
        return await asyncio.to_thread(
            self.chat, messages, model=model, temperature=temperature, max_tokens=max_tokens
        )

    # ------------------------------------------------------------------
    # Streaming API. Default fallback replays a full completion as one
    # chunk, so every provider streams even before a native
    # implementation lands. Providers with true streaming override these.
    # ------------------------------------------------------------------
    def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[StreamChunk]:
        """Yield text deltas (blocking generator)."""
        result = self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        if result.content:
            yield StreamChunk(
                delta=result.content,
                provider=result.provider,
                model=result.model,
            )

    async def astream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Yield text deltas asynchronously. Used by the SSE endpoint."""
        result = await self.achat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        if result.content:
            yield StreamChunk(
                delta=result.content,
                provider=result.provider,
                model=result.model,
            )

    # ------------------------------------------------------------------
    # Convenience helpers built on top of chat — shared by all providers.
    # ------------------------------------------------------------------
    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Single-prompt completion (wraps :meth:`chat`)."""
        messages: list[ChatMessage] = []
        if system:
            messages.append(ChatMessage(role=ChatRole.SYSTEM, content=system))
        messages.append(ChatMessage(role=ChatRole.USER, content=prompt))
        return self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)

    async def acomplete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Async single-prompt completion (wraps :meth:`achat`)."""
        messages: list[ChatMessage] = []
        if system:
            messages.append(ChatMessage(role=ChatRole.SYSTEM, content=system))
        messages.append(ChatMessage(role=ChatRole.USER, content=prompt))
        return await self.achat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
