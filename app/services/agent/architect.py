"""Agent Architect.

The Architect converts an AgentVersion + user task into a structured,
provider-neutral ExecutionPlan.

It does not execute tools, run commands, discover integrations, or evaluate
results. Those responsibilities belong to later stages of the agent runtime.
"""

from __future__ import annotations

import json
from typing import Any

import neatlogs

from app.schemas.agent_version import AgentVersion
from app.schemas.plan import ExecutionPlan
from app.services.llm import service as llm_service
from app.services.llm.base import (
    ChatMessage,
    ChatRole,
    LLMProvider,
)


class AgentArchitectError(Exception):
    """Base exception for Agent Architect failures."""


class AgentPlanError(AgentArchitectError):
    """Raised when the model produces an invalid execution plan."""


class AgentArchitect:
    """Build structured plans for agent tasks."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @neatlogs.span(
        kind="AGENT",
        name="agent.architect",
    )
    async def build_plan(
        self,
        agent_version: AgentVersion,
        task: str,
        *,
        available_tools: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        """Create an execution plan for a task."""

        if not task.strip():
            raise AgentPlanError("Task must not be empty.")

        tools = available_tools or []
        extra_context = context or {}

        prompt = self._build_prompt(
            agent_version=agent_version,
            task=task,
            available_tools=tools,
            context=extra_context,
        )

        try:
            response = await llm_service.achat(
              messages=[
                  ChatMessage(
                      role=ChatRole.SYSTEM,
                      content=self._system_instruction(),
                  ),
                  ChatMessage(
                      role=ChatRole.USER,
                      content=prompt,
                  ),
              ],
              provider=self._provider,
              model=agent_version.model,
              temperature=0.2,
              max_tokens=agent_version.max_tokens,
            )
        except Exception as exc:
            raise AgentArchitectError(
                f"Failed to generate agent plan: {exc}"
            ) from exc

        if not response.content.strip():
            raise AgentPlanError(
                f"Architect model '{response.model}' from "
                f"provider '{response.provider}' returned an empty response."
            )
        
        return self._parse_plan(response.content)

    @staticmethod
    def _system_instruction() -> str:
        return """You are Accord's Agent Architect.

Your job is to convert a user's task into a concise, actionable execution plan.

You are planning actions, not revealing private reasoning.

Rules:
1. Return ONLY valid JSON.
2. Do not return Markdown or code fences.
3. Never include chain-of-thought or private reasoning.
4. Every step must describe an observable action or required outcome.
5. Use "execute" only when actual command execution is required.
6. Use "tool" when an external capability is required.
7. Use "prepare" for setup or data preparation.
8. Use "respond" for the final user-facing response.
9. Keep the plan as small as possible while still completing the task.
10. Respect the supplied agent instructions.
11. Do not invent unavailable tools.
12. If no tool is available for a capability, describe the needed capability
    rather than fabricating a tool implementation.

The JSON must have exactly this top-level structure:

{
  "goal": "string",
  "steps": [
    {
      "id": "string",
      "kind": "prepare | execute | tool | respond",
      "instruction": "string",
      "depends_on": ["step-id"],
      "tool_name": "string or null",
      "command": "string or null",
      "args": [],
      "expected_output": "string or null",
      "metadata": {}
    }
  ],
  "final_response": "string",
  "metadata": {}
}
"""

    @classmethod
    def _build_prompt(
        cls,
        agent_version: AgentVersion,
        task: str,
        available_tools: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> str:
        payload = {
            "agent_instructions": agent_version.system_prompt or "",
            "user_task": task,
            "available_tools": available_tools,
            "context": context,
        }

        return (
            "Create an execution plan for the following agent request.\n\n"
            "Input:\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}"
        )

    @staticmethod
    def _parse_plan(content: str) -> ExecutionPlan:
        """Parse and validate structured Architect output."""
    
        if not content or not content.strip():
            raise AgentPlanError(
                "Architect returned an empty response."
            )
    
        cleaned = content.strip()
    
        # Remove Markdown code fences.
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
    
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
    
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
    
            cleaned = "\n".join(lines).strip()
    
        # First attempt: entire response is JSON.
        try:
            raw = json.loads(cleaned)
        except json.JSONDecodeError:
            # Second attempt: extract the outermost JSON object.
            start = cleaned.find("{")
            end = cleaned.rfind("}")
    
            if start == -1 or end == -1 or end <= start:
                raise AgentPlanError(
                    "Architect returned no valid JSON object."
                )
    
            try:
                raw = json.loads(
                    cleaned[start : end + 1]
                )
            except json.JSONDecodeError as exc:
                raise AgentPlanError(
                    f"Architect returned invalid JSON: {exc}"
                ) from exc
    
        try:
            plan = ExecutionPlan.model_validate(raw)
        except Exception as exc:
            raise AgentPlanError(
                f"Architect returned an invalid plan: {exc}"
            ) from exc
    
        AgentArchitect._validate_dependencies(plan)
    
        return plan

    @staticmethod
    def _validate_dependencies(
        plan: ExecutionPlan,
    ) -> None:
        """Validate dependency references and step identifiers."""

        step_ids = [step.id for step in plan.steps]

        if len(step_ids) != len(set(step_ids)):
            raise AgentPlanError(
                "Architect returned duplicate step IDs."
            )

        known_ids = set(step_ids)

        for step in plan.steps:
            missing = set(step.depends_on) - known_ids

            if missing:
                raise AgentPlanError(
                    f"Step '{step.id}' references unknown dependencies: "
                    f"{sorted(missing)}"
                )

            if step.kind.value == "execute" and not step.command:
                raise AgentPlanError(
                    f"Execute step '{step.id}' requires a command."
                )

            if step.kind.value == "tool" and not step.tool_name:
                raise AgentPlanError(
                    f"Tool step '{step.id}' requires tool_name."
                )