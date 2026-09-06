"""Model-driven LLM provider resolution.

The application chooses models, not vendors.

Examples:

    zai-org/GLM-4.7-Flash -> TensorMux
    gemini-3.8-flash      -> Google

Provider-specific credentials are selected automatically.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.llm.base import (
    LLMConfigError,
    LLMProvider,
)
from app.services.llm.google import (
    DEFAULT_MODEL as GOOGLE_DEFAULT_MODEL,
    GoogleProvider,
)
from app.services.llm.tensormux import (
    DEFAULT_MODEL as TENSORMUX_DEFAULT_MODEL,
    TensorMuxProvider,
    normalize_base_url,
)


def _secret(value: object) -> str | None:
    """Unwrap SecretStr | str | None."""

    if value is None:
        return None

    getter = getattr(
        value,
        "get_secret_value",
        None,
    )

    if callable(getter):
        value = getter()

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return None


def _configured_tensormux_model(
    cfg: Settings,
) -> str:
    return (
        cfg.tensormux_model.strip()
        or TENSORMUX_DEFAULT_MODEL
    )


def _configured_google_model(
    cfg: Settings,
) -> str:
    return (
        cfg.google_model.strip()
        or GOOGLE_DEFAULT_MODEL
    )


def resolve_model_provider(
    model: str,
    cfg: Settings | None = None,
) -> str:
    """Determine which provider owns a model ID."""

    if not model or not model.strip():
        raise LLMConfigError(
            "A model must be specified."
        )

    cfg = cfg or get_settings()
    model = model.strip()

    tensormux_model = _configured_tensormux_model(cfg)
    google_model = _configured_google_model(cfg)

    if model == tensormux_model:
        return "tensormux"

    if model == google_model:
        return "google"

    # Sensible model-family routing for explicitly supplied model IDs.
    lowered = model.lower()

    if lowered.startswith("gemini-"):
        return "google"

    if lowered.startswith("gemma-"):
        return "google"

    # TensorMux can expose many OpenAI-compatible model IDs. Keep
    # non-Google model IDs on TensorMux unless explicitly configured
    # otherwise in a future model registry.
    return "tensormux"


def create_provider_for_model(
    model: str,
    cfg: Settings | None = None,
) -> LLMProvider:
    """Create the concrete provider required for a model."""

    cfg = cfg or get_settings()

    provider = resolve_model_provider(
        model,
        cfg,
    )

    if provider == "tensormux":
        api_key = (
            _secret(cfg.tensormux_api_key)
            or _secret(cfg.llm_api_key)
        )

        if not api_key:
            raise LLMConfigError(
                "TensorMux API key is missing. "
                "Set TENSORMUX_API_KEY."
            )

        base_url = (
            _secret(cfg.llm_base_url)
            or cfg.tensormux_base_url
            or ""
        ).strip()

        return TensorMuxProvider(
            api_key=api_key,
            base_url=normalize_base_url(
                base_url
            ),
            model=model,
            temperature=cfg.llm_temperature,
            max_tokens=cfg.llm_max_tokens,
        )

    api_key = (
        _secret(cfg.google_api_key)
        or _secret(cfg.llm_api_key)
    )

    if not api_key:
        raise LLMConfigError(
            "Google API key is missing. "
            "Set GOOGLE_API_KEY."
        )

    return GoogleProvider(
        api_key=api_key,
        model=model,
        temperature=cfg.llm_temperature,
        max_tokens=cfg.llm_max_tokens,
    )


@lru_cache(maxsize=16)
def get_llm_provider_for_model(
    model: str,
) -> LLMProvider:
    """Return the provider for a specific model."""

    return create_provider_for_model(
        model,
        get_settings(),
    )


def get_primary_model(
    cfg: Settings | None = None,
) -> str:
    """Return the model used for new agent versions."""

    cfg = cfg or get_settings()

    if cfg.llm_primary_model:
        return cfg.llm_primary_model.strip()

    # Provider setting is retained only as a backwards-compatible
    # migration path for existing deployments.
    if cfg.llm_provider == "google":
        return _configured_google_model(cfg)

    return _configured_tensormux_model(cfg)


def get_fallback_models(
    cfg: Settings | None = None,
) -> list[str]:
    """Return fallback models in priority order."""

    cfg = cfg or get_settings()

    return [
        model
        for model in cfg.fallback_model_list
        if model
    ]


def get_llm() -> LLMProvider:
    """Return the primary provider for backwards compatibility."""

    model = get_primary_model()

    return get_llm_provider_for_model(model)


def reset_llm_provider_cache() -> None:
    """Clear cached provider instances."""

    get_llm_provider_for_model.cache_clear()