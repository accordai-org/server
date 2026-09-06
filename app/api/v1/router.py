"""Aggregate router for all `/api/v1` endpoints.

Import endpoint routers here and include them on `api_v1_router`.
Routers must stay thin — no business logic, just HTTP wiring.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, sandbox, runs, agent, agents, marketplace

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(sandbox.router)
api_v1_router.include_router(runs.router)
api_v1_router.include_router(agent.router)
api_v1_router.include_router(agents.router)
api_v1_router.include_router(marketplace.router)
