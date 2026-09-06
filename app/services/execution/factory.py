"""Execution provider resolution.

The factory is intentionally provider-agnostic at the public boundary.
Concrete providers are registered here as they are implemented.
"""

from __future__ import annotations

from app.config import settings
from app.services.execution.base import (
    ExecutionConfigurationError,
    ExecutionProvider,
)


def get_execution_provider(
    provider_name: str | None = None,
) -> ExecutionProvider:
    """Resolve the configured execution provider.

    Task 7 defines the abstraction but does not ship a concrete provider.
    Task 8 will register the E2B implementation here.
    """
    name = provider_name or settings.execution_provider

    raise ExecutionConfigurationError(
        f"Execution provider '{name}' is not implemented yet."
    )