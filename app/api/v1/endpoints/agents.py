"""Agent catalog endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas.agent import Agent
from app.services.agent.store import agent_store


router = APIRouter(
    prefix="/agents",
    tags=["agents"],
)


def _stats(agent: Agent) -> dict:
    runs = agent_store.agent_runs(agent.id)

    completed = [
        run
        for run in runs
        if run.status.value == "succeeded"
    ]

    success_rate = (
        len(completed) / len(runs)
        if runs
        else 0.0
    )

    return {
        "runs": len(runs),
        "successRate": f"{success_rate * 100:.0f}%",
        "accuracy": success_rate,
        "lastRun": (
            runs[-1].ended_at.isoformat()
            if runs and runs[-1].ended_at
            else "—"
        ),
    }


@router.get("/mine")
async def list_my_agents() -> dict:
    agents = []

    for agent in agent_store.list_agents():
        stats = _stats(agent)

        agents.append(
            {
                "id": str(agent.id),
                "name": agent.name,
                "description": agent.description,
                "status": agent.status.value,
                "visibility": (
                    "Public"
                    if agent.metadata.get("public")
                    else "Private"
                ),
                **stats,
            }
        )

    return {
        "items": agents,
    }


@router.get("/{agent_id}")
async def get_agent(
    agent_id: UUID,
) -> dict:
    agent = agent_store.get_agent(agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found.",
        )

    stats = _stats(agent)

    version = agent_store.get_agent_version(
        agent
    )

    return {
        "agent": {
            "id": str(agent.id),
            "name": agent.name,
            "description": agent.description,
            "status": agent.status.value,
            **stats,
            "tokenUsage": "—",
            "cost": "—",
            "earnings": "—",
            "memories": [],
            "toolUsage": [],
            "version": (
                version.version
                if version
                else None
            ),
        }
    }