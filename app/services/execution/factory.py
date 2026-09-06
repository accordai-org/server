"""Execution provider resolution."""

from __future__ import annotations

from app.config import settings
from app.services.execution.base import (
    ExecutionConfigurationError,
    ExecutionProvider,
)
from app.services.execution.e2b import E2BExecutionProvider


def get_execution_provider(
    provider_name: str | None = None,
) -> ExecutionProvider:
    """Return the configured execution provider."""

    name = provider_name or settings.execution_provider

    if name == "e2b":
        api_key = (
            settings.execution_api_key.get_secret_value()
            if settings.execution_api_key is not None
            else None
        )

        return E2BExecutionProvider(
            api_key=api_key,
            base_url=settings.execution_base_url,
            default_timeout_seconds=settings.execution_timeout_seconds,
        )

    raise ExecutionConfigurationError(
        f"Execution provider '{name}' is not supported."
    )