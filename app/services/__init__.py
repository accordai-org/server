"""Business logic layer. Routers call into here; no FastAPI imports."""

from app.services import health_service

__all__ = ["health_service"]
