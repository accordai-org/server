"""Discover and resolve tools available to an agent."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.agent_version import AgentVersion
from app.schemas.connection import (
    AgentConnectionBinding,
    Connection,
)
from app.schemas.plan import (
    ExecutionPlan,
    ResolvedTool,
    ToolResolution,
    UnresolvedTool,
)
from app.schemas.tool import AgentToolBinding, Tool
from app.services.connections.registry import ConnectionRegistry


class ToolDiscoveryError(Exception):
    """Base error for tool discovery."""


class ToolDiscovery:
    """Resolve plan tool requirements against agent connections and tools."""

    def __init__(
        self,
        registry: ConnectionRegistry | None = None,
    ) -> None:
        self._registry = registry or ConnectionRegistry()

    async def discover(
        self,
        agent_version: AgentVersion,
        connections: Sequence[Connection],
        connection_bindings: Sequence[AgentConnectionBinding],
    ) -> list[Tool]:
        """Discover all tools available through an agent's connections."""

        active_connections = {
            connection.id: connection
            for connection in connections
            if connection.status.value == "active"
        }

        tools: list[Tool] = []

        ordered_bindings = sorted(
            (
                binding
                for binding in connection_bindings
                if (
                    binding.agent_version_id == agent_version.id
                    and binding.is_enabled
                )
            ),
            key=lambda binding: (
                binding.order is None,
                binding.order or 0,
            ),
        )

        for binding in ordered_bindings:
            connection = active_connections.get(
                binding.connection_id
            )

            if connection is None:
                continue

            provider = self._registry.get(connection.kind)

            discovered = await provider.discover_tools(
                connection
            )

            tools.extend(discovered)

        return tools

    def resolve(
        self,
        agent_version: AgentVersion,
        plan: ExecutionPlan,
        tools: Sequence[Tool],
        bindings: Sequence[AgentToolBinding],
    ) -> ToolResolution:
        """Resolve tools requested by an execution plan."""

        active_tools = {
            tool.id: tool
            for tool in tools
            if tool.is_active
        }

        bindings_by_tool_id = {
            binding.tool_id: binding
            for binding in bindings
            if (
                binding.agent_version_id == agent_version.id
                and binding.is_enabled
            )
        }

        resolved: list[ResolvedTool] = []
        unresolved: list[UnresolvedTool] = []

        for step in plan.steps:
            if step.tool_name is None:
                continue

            match = next(
                (
                    tool
                    for tool in active_tools.values()
                    if (
                        tool.slug == step.tool_name
                        or tool.name == step.tool_name
                    )
                ),
                None,
            )

            if match is None:
                unresolved.append(
                    UnresolvedTool(
                        name=step.tool_name,
                        reason=(
                            "Tool is not available through this "
                            "agent's connections."
                        ),
                    )
                )
                continue

            binding = bindings_by_tool_id.get(match.id)

            if binding is None:
                unresolved.append(
                    UnresolvedTool(
                        name=step.tool_name,
                        reason=(
                            "Tool is not enabled for this agent version."
                        ),
                    )
                )
                continue

            resolved.append(
                ResolvedTool(
                    tool=match,
                    config=dict(binding.config_overrides),
                )
            )

        return ToolResolution(
            resolved=resolved,
            unresolved=unresolved,
        )