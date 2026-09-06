"""Health / readiness business logic.

Kept separate from routers so it can be unit-tested and reused
without any HTTP layer.
"""

from app.config import settings
from app.schemas.health import HealthResponse, ReadinessResponse


def get_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
    )


def get_readiness() -> ReadinessResponse:
    # No external dependencies wired yet — extend `checks` as
    # database, queue, or provider probes are added.
    checks: dict[str, str] = {"app": "ready"}
    ready = all(value == "ready" for value in checks.values())
    return ReadinessResponse(ready=ready, checks=checks)
