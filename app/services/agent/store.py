"""Temporary process-local agent catalog.

This is intentionally storage-agnostic. Replace this implementation with a
database repository later without changing AgentRuntime or the API contracts.
"""

from __future__ import annotations

from uuid import UUID

from app.schemas.agent import Agent
from app.schemas.agent_version import AgentVersion
from app.schemas.run import Run


class AgentStore:
    def __init__(self) -> None:
        self.agents: dict[UUID, Agent] = {}
        self.versions: dict[UUID, AgentVersion] = {}
        self.runs: dict[UUID, Run] = {}

    def save_agent(
        self,
        agent: Agent,
    ) -> Agent:
        self.agents[agent.id] = agent
        return agent

    def save_version(
        self,
        version: AgentVersion,
    ) -> AgentVersion:
        self.versions[version.id] = version
        return version

    def save_run(
        self,
        run: Run,
    ) -> Run:
        self.runs[run.id] = run
        return run

    def get_agent(
        self,
        agent_id: UUID,
    ) -> Agent | None:
        return self.agents.get(agent_id)

    def get_version(
        self,
        version_id: UUID,
    ) -> AgentVersion | None:
        return self.versions.get(version_id)

    def get_agent_version(
        self,
        agent: Agent,
    ) -> AgentVersion | None:
        if agent.current_version_id is None:
            return None

        return self.versions.get(
            agent.current_version_id
        )

    def list_agents(self) -> list[Agent]:
        return list(self.agents.values())

    def agent_runs(
        self,
        agent_id: UUID,
    ) -> list[Run]:
        return [
            run
            for run in self.runs.values()
            if run.agent_id == agent_id
        ]


agent_store = AgentStore()