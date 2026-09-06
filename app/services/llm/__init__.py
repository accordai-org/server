"""Vendor-neutral LLM access.

Import the interface and entry points from here::

    from app.services.llm import LLMProvider, ChatMessage, get_llm, get_llm_provider

Never import ``app.services.llm.tensormux`` or ``app.services.llm.google``
outside this package — use :func:`get_llm_provider` / :func:`get_llm`
so callers stay decoupled from vendors.
"""

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
from app.services.llm.factory import (
    SUPPORTED_PROVIDERS,
    SupportedProvider,
    create_provider,
    get_llm,
    get_llm_provider,
    reset_llm_provider_cache,
)

__all__ = [
    "ChatMessage",
    "ChatRole",
    "LLMConfigError",
    "LLMError",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "LLMUsage",
    "StreamChunk",
    "SUPPORTED_PROVIDERS",
    "SupportedProvider",
    "create_provider",
    "get_llm",
    "get_llm_provider",
    "reset_llm_provider_cache",
]
