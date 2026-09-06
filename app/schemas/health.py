"""Schemas for health and readiness responses."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    env: str


class ReadinessResponse(BaseModel):
    ready: bool
    checks: dict[str, str] = {}
