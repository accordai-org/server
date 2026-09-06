"""Health and readiness endpoints.

Thin HTTP layer only — all status computation lives in
`app.services.health_service`.
"""

from fastapi import APIRouter

from app.schemas.health import HealthResponse, ReadinessResponse
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
def health() -> HealthResponse:
    return health_service.get_health()


@router.get("/readiness", response_model=ReadinessResponse, summary="Readiness check")
def readiness() -> ReadinessResponse:
    return health_service.get_readiness()
