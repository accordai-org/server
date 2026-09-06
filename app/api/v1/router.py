"""Aggregate router for all `/api/v1` endpoints.

Import endpoint routers here and include them on `api_v1_router`.
Routers must stay thin — no business logic, just HTTP wiring.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import chat, health, sandbox, runs

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(sandbox.router)
api_v1_router.include_router(runs.router)
