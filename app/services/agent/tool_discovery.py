from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.schemas.plan import ExecutionPlan
from app.schemas.tool import AgentToolBinding, Tool
from app.schemas.agent_version import AgentVersion


class ToolDiscoveryError(Exception):
    """Base error for tool discovery."""


class ToolDiscovery:
    """Resolve tools requested by an execution plan."""

    def resolve(
        self,
        agent_version: AgentVersion,
        plan: ExecutionPlan,
        tools: Sequence[Tool],
        bindings: Sequence[AgentToolBinding],
    ):
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

        resolved = []
        unresolved = []

        for step in plan.steps:
            if step.tool_name is None:
                continue

            match = None

            for tool in active_tools.values():
                if (
                    tool.slug == step.tool_name
                    or tool.name == step.tool_name
                ):
                    match = tool
                    break

            if match is None:
                unresolved.append(
                    {
                        "name": step.tool_name,
                        "reason": "Tool is not available in the catalog.",
                    }
                )
                continue

            binding = bindings_by_tool_id.get(match.id)

            if binding is None:
                unresolved.append(
                    {
                        "name": step.tool_name,
                        "reason": "Tool is not enabled for this agent version.",
                    }
                )
                continue

            resolved.append(
                {
                    "tool": match,
                    "config": dict(binding.config_overrides),
                }
            )

        from app.schemas.plan import (
            ResolvedTool,
            ToolResolution,
            UnresolvedTool,
        )

        return ToolResolution(
            resolved=[
                ResolvedTool(**item)
                for item in resolved
            ],
            unresolved=[
                UnresolvedTool(**item)
                for item in unresolved
            ],
        )