"""Marketplace endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.agent.store import agent_store


router = APIRouter(
    prefix="/marketplace",
    tags=["marketplace"],
)


@router.get("/agents")
async def marketplace_agents(
    q: str | None = Query(
        default=None,
        max_length=120,
    ),
    type: str | None = Query(
        default=None,
        max_length=60,
    ),
) -> dict:
    del type

    query = (
        q.strip().lower()
        if q
        else None
    )

    agents = []

    for agent in agent_store.list_agents():
        if not agent.metadata.get(
            "public",
            False,
        ):
            continue

        if query:
            haystack = (
                f"{agent.name} "
                f"{agent.description or ''}"
            ).lower()

            if query not in haystack:
                continue

        agents.append(
            {
                "id": str(agent.id),
                "name": agent.name,
                "type": "Agent",
                "description": (
                    agent.description
                    or ""
                ),
                "users": "0",
                "author": "Community",
            }
        )

    return {
        "items": agents,
    }