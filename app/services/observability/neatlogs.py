"""NeatLogs lifecycle and instrumentation.

NeatLogs is initialized once for the lifetime of the server process.
LLM clients are wrapped at construction time so provider calls are
automatically captured as child LLM spans.

Application-level agent/tool spans should use NeatLogs directly from
the service layer rather than coupling routers to observability.
"""

from __future__ import annotations

import logging
from typing import Any

import neatlogs

from app.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def initialize_neatlogs() -> None:
    """Initialize NeatLogs once for the current server process.

    This function is intentionally safe to call more than once because
    FastAPI/test environments can create application instances multiple
    times.
    """
    global _initialized

    if _initialized:
        return

    if not settings.neatlogs_enabled:
        logger.info("NeatLogs integration is disabled.")
        return

    try:
        neatlogs.init(**settings.neatlogs_init_kwargs)
    except Exception:
        logger.exception("Failed to initialize NeatLogs.")
        raise

    _initialized = True
    logger.info(
        "NeatLogs initialized",
        extra={
            "workflow_name": settings.neatlogs_workflow_name,
            "endpoint": settings.neatlogs_endpoint,
        },
    )


def shutdown_neatlogs() -> None:
    """Flush and shut down NeatLogs during application shutdown."""
    global _initialized

    if not _initialized:
        return

    try:
        neatlogs.flush()
    finally:
        neatlogs.shutdown()
        _initialized = False


def wrap_client(client: Any, **metadata: Any) -> Any:
    """Wrap an LLM client with NeatLogs when observability is enabled.

    NeatLogs handles the actual LLM span creation. The metadata is attached
    to the workflow root so future Accord traces can be filtered by provider,
    route, or other application-specific dimensions.
    """
    if not settings.neatlogs_enabled:
        return client

    if not _initialized:
        raise RuntimeError(
            "NeatLogs has not been initialized. "
            "Call initialize_neatlogs() during application startup."
        )

    return neatlogs.wrap(client, **metadata)