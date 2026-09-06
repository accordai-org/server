"""Provider factory + FastAPI dependency.

This is the **only** place outside the provider modules that may import
concrete providers. The rest of the application depends solely on the
:class:`LLMProvider <app.services.llm.base.LLMProvider>` interface and
obtains instances via :func:`get_llm_provider` (or the :func:`get_llm`
FastAPI dependency).

Configuration resolution (all values originate from env / ``.env`` via
``app.config.Settings``)::

    provider = LLM_PROVIDER (``"tensormux"`` | ``"google"``)
    tensormux: api_key = TENSORMUX_API_KEY or LLM_API_KEY
               base_url = LLM_BASE_URL or TENSORMUX_BASE_URL
               model    = LLM_MODEL or TENSORMUX_MODEL
    google:    api_key = GOOGLE_API_KEY or LLM_API_KEY
               model    = LLM_MODEL or GOOGLE_MODEL

``LLM_MODEL`` / ``LLM_API_KEY`` / ``LLM_BASE_URL`` are generic overrides;
provider-specific variables win for keys/URLs, while an explicitly set
``LLM_MODEL`` wins for the model (so one variable can switch models
without touching provider sections).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from app.config import Settings, get_settings
from app.services.llm.base import LLMConfigError, LLMProvider
from app.services.llm.google import DEFAULT_MODEL as GOOGLE_DEFAULT_MODEL
from app.services.llm.google import GoogleProvider
from app.services.llm.tensormux import DEFAULT_MODEL as TENSORMUX_DEFAULT_MODEL
from app.services.llm.tensormux import TensorMuxProvider, normalize_base_url

SupportedProvider = Literal["tensormux", "google"]
SUPPORTED_PROVIDERS: tuple[str, ...] = ("tensormux", "google")


def _secret(value: object) -> str | None:
    """Unwrap ``SecretStr | str | None`` to a plain string (or ``None``)."""
    if value is None:
        return None
    get_secret = getattr(value, "get_secret_value", None)
    if callable(get_secret):
        candidate = get_secret()
        return candidate or None
    if isinstance(value, str):
        return value or None
    return None


def _generic_model_override() -> str | None:
    """Return ``LLM_MODEL`` only when it was explicitly set in the environment."""
    raw = os.getenv("LLM_MODEL")
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def create_provider(
    name: str,
    settings: Settings | None = None,
) -> LLMProvider:
    """Build a concrete provider but return it as the interface type."""
    resolved = (name or "").strip().lower()
    if resolved not in SUPPORTED_PROVIDERS:
        raise LLMConfigError(
            f"Unknown LLM provider '{name}'. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}. "
            "Set LLM_PROVIDER in the environment."
        )
    cfg = settings or get_settings()
    generic_model = _generic_model_override()
    # Fall back to the parsed Settings value when tests inject Settings
    # directly without touching the real environment.
    if generic_model is None and getattr(cfg, "llm_model", None):
        generic_model = str(cfg.llm_model).strip() or None

    if resolved == "tensormux":
        api_key = _secret(cfg.tensormux_api_key) or _secret(cfg.llm_api_key)
        base_url = (_secret(cfg.llm_base_url) or cfg.tensormux_base_url or "").strip()
        model = generic_model or (cfg.tensormux_model or "").strip() or TENSORMUX_DEFAULT_MODEL
        return TensorMuxProvider(
            api_key=api_key,
            base_url=normalize_base_url(base_url),
            model=model,
            temperature=cfg.llm_temperature,
            max_tokens=cfg.llm_max_tokens,
        )

    # resolved == "google"
    api_key = _secret(cfg.google_api_key) or _secret(cfg.llm_api_key)
    model = generic_model or (cfg.google_model or "").strip() or GOOGLE_DEFAULT_MODEL
    return GoogleProvider(
        api_key=api_key,
        model=model,
        temperature=cfg.llm_temperature,
        max_tokens=cfg.llm_max_tokens,
    )


@lru_cache(maxsize=4)
def get_llm_provider(name: str | None = None) -> LLMProvider:
    """Return the cached provider for ``name`` (defaults to ``LLM_PROVIDER``)."""
    settings = get_settings()
    return create_provider(name or settings.llm_provider, settings)


def reset_llm_provider_cache() -> None:
    """Clear the :func:`get_llm_provider` cache (tests / settings reload)."""
    get_llm_provider.cache_clear()


def get_llm() -> LLMProvider:
    """FastAPI dependency. Inject as ``Depends(get_llm)`` — typed as the interface."""

    return get_llm_provider()
