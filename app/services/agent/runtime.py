"""End-to-end Accord agent runtime.

The runtime coordinates agent planning, tool discovery, execution,
evaluation, and event publication. It owns orchestration; concrete
providers remain behind their respective abstractions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import neatlogs

from app.config import settings
from app.schemas.agent import Agent
from app.schemas.agent_version import AgentVersion
from app.schemas.enums import AgentStatus, RunStatus
from app.schemas.plan import ExecutionPlan
from app.schemas.run import Run, RunError
from app.schemas.run_event import RunEvent, RunEventKind
from app.services.agent.architect import AgentArchitect
from app.services.agent.store import agent_store
from app.services.events import event_bus
from app.services.evaluation.evaluator import (
    AgentEvaluator,
    EvaluationError,
)
from app.services.execution import (
    ExecutionProvider,
    ExecutionRequest,
    ExecutionTask,
    get_execution_provider,
)
from app.services.llm import get_llm
from app.services.llm.base import (
    ChatMessage,
    ChatRole,
)
from app.services.llm import service as llm_service


class AgentRuntimeError(Exception):
    """Base exception for agent runtime failures."""


class AgentRuntime:
    """Coordinates one complete Accord agent run."""

    def __init__(
        self,
        *,
        execution_provider: ExecutionProvider | None = None,
    ) -> None:
        llm_provider = get_llm()

        self._architect = AgentArchitect(llm_provider)
        self._evaluator = AgentEvaluator(llm_provider)

        self._execution = (
            execution_provider
            or get_execution_provider()
        )

    def prepare_run(
        self,
        *,
        prompt: str,
        agent_id: UUID | None = None,
        tools: list[str] | None = None,
        skills: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> Run:
        """Create and persist a queued run without starting execution."""

        agent, version = self._resolve_agent(
            prompt=prompt,
            agent_id=agent_id,
        )

        run = Run(
            agent_id=agent.id,
            agent_version_id=version.id,
            status=RunStatus.QUEUED,
            inputs={
                "prompt": prompt,
                "tools": tools or [],
                "skills": skills or [],
                "history": history or [],
            },
            started_at=self._now(),
            triggered_by="chat",
        )

        agent_store.save_run(run)

        return run

    @neatlogs.span(
        kind="AGENT",
        name="agent.run",
    )
    async def run(
        self,
        *,
        prompt: str,
        agent_id: UUID | None = None,
        tools: list[str] | None = None,
        skills: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> Run:
        """Prepare and execute a new agent run."""

        run = self.prepare_run(
            prompt=prompt,
            agent_id=agent_id,
            tools=tools,
            skills=skills,
            history=history,
        )

        return await self.execute_run(run)

    @neatlogs.span(
        kind="AGENT",
        name="agent.execute_run",
    )
    async def execute_run(
        self,
        run: Run,
    ) -> Run:
        """Execute a previously prepared run."""

        version = agent_store.get_version(
            run.agent_version_id
        )

        if version is None:
            raise AgentRuntimeError(
                f"Agent version '{run.agent_version_id}' was not found."
            )

        prompt = str(
            run.inputs.get(
                "prompt",
                "",
            )
        )

        requested_tools = run.inputs.get(
            "tools",
            [],
        )

        if not isinstance(requested_tools, list):
            requested_tools = []

        skills = run.inputs.get(
            "skills",
            [],
        )

        if not isinstance(skills, list):
            skills = []

        history = run.inputs.get(
            "history",
            [],
        )

        if not isinstance(history, list):
            history = []

        run.status = RunStatus.RUNNING
        run.started_at = self._now()
        agent_store.save_run(run)

        await self._publish(
            run,
            RunEventKind.RUN_STARTED,
            {
                "agent_id": str(run.agent_id),
                "agent_version_id": str(
                    run.agent_version_id
                ),
            },
        )

        try:
            memories: list[Any] = []

            await self._publish_step(
                run,
                "Planning your agent workflow…",
            )

            available_tools = [
                {
                    "name": tool_name,
                    "description": (
                        "Tool selected for this agent run."
                    ),
                }
                for tool_name in requested_tools
            ]

            plan = await self._architect.build_plan(
                version,
                prompt,
                available_tools=available_tools,
                context={
                    "history": history,
                    "memories": memories,
                    "skills": skills,
                },
            )

            await self._publish(
                run,
                RunEventKind.PLAN_CREATED,
                {
                    "goal": plan.goal,
                    "steps": [
                        step.model_dump()
                        for step in plan.steps
                    ],
                },
            )

            execution_context: list[
                dict[str, Any]
            ] = []

            for step in plan.steps:
                if step.kind.value == "execute":
                    await self._execute_step(
                        run=run,
                        step=step,
                        execution_context=execution_context,
                    )

                elif step.kind.value == "tool":
                    await self._handle_tool_step(
                        run=run,
                        step=step,
                        execution_context=execution_context,
                    )

            await self._publish_step(
                run,
                "Generating your agent response…",
            )

            final_response = await self._generate_response(
                version=version,
                prompt=prompt,
                plan=plan,
                execution_context=execution_context,
                history=history,
            )

            run.outputs = {
                "content": final_response,
                "plan": plan.model_dump(),
                "execution": execution_context,
            }

            run.status = RunStatus.SUCCEEDED
            run.ended_at = self._now()

            await self._evaluate(
                run=run,
                version=version,
                prompt=prompt,
                plan=plan,
                execution_context=execution_context,
            )

            agent_store.save_run(run)

            await self._publish(
                run,
                RunEventKind.RUN_COMPLETED,
                {
                    "content": final_response,
                    "agent_id": str(run.agent_id),
                    "agent_version_id": str(
                        run.agent_version_id
                    ),
                },
            )

            return run

        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = RunError(
                code="AGENT_RUN_FAILED",
                message=str(exc),
                retryable=False,
            )
            run.ended_at = self._now()

            agent_store.save_run(run)

            await self._publish(
                run,
                RunEventKind.RUN_FAILED,
                {
                    "message": str(exc),
                },
            )

            raise AgentRuntimeError(
                f"Agent run failed: {exc}"
            ) from exc

        finally:
            await event_bus.close_run(run.id)

    async def _execute_step(
        self,
        *,
        run: Run,
        step: Any,
        execution_context: list[dict[str, Any]],
    ) -> None:
        """Execute one sandbox step."""

        await self._publish_step(
            run,
            "Testing your agent in sandbox…",
        )

        await self._publish(
            run,
            RunEventKind.EXECUTION_STARTED,
            {
                "step_id": step.id,
                "command": step.command,
                "args": step.args,
            },
        )

        environment = await self._execution.create_environment(
            ExecutionRequest(
                image="base",
                working_directory="/workspace",
                timeout_seconds=(
                    settings.execution_timeout_seconds
                ),
            )
        )

        try:
            result = await self._execution.execute(
                environment,
                ExecutionTask(
                    command=step.command or "true",
                    args=step.args,
                    working_directory="/workspace",
                ),
            )

            execution_context.append(
                {
                    "step_id": step.id,
                    "type": "execution",
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                }
            )

            if result.stdout:
                await self._publish(
                    run,
                    RunEventKind.EXECUTION_STDOUT,
                    {
                        "step_id": step.id,
                        "content": result.stdout,
                    },
                )

            if result.stderr:
                await self._publish(
                    run,
                    RunEventKind.EXECUTION_STDERR,
                    {
                        "step_id": step.id,
                        "content": result.stderr,
                    },
                )

            if (
                result.exit_code == 0
                and not result.timed_out
            ):
                await self._publish(
                    run,
                    RunEventKind.EXECUTION_COMPLETED,
                    {
                        "step_id": step.id,
                        "exit_code": result.exit_code,
                    },
                )
            else:
                await self._publish(
                    run,
                    RunEventKind.EXECUTION_FAILED,
                    {
                        "step_id": step.id,
                        "exit_code": result.exit_code,
                        "timed_out": result.timed_out,
                        "stderr": result.stderr,
                    },
                )

        finally:
            await self._execution.destroy_environment(
                environment
            )

    async def _handle_tool_step(
        self,
        *,
        run: Run,
        step: Any,
        execution_context: list[dict[str, Any]],
    ) -> None:
        """Record a tool request until concrete tool execution is wired."""

        tool_name = step.tool_name

        await self._publish_step(
            run,
            f"Using {tool_name or 'connected tool'}…",
        )

        await self._publish(
            run,
            RunEventKind.TOOL_STARTED,
            {
                "step_id": step.id,
                "tool": tool_name,
            },
        )

        execution_context.append(
            {
                "step_id": step.id,
                "type": "tool",
                "tool": tool_name,
                "status": "unavailable",
            }
        )

        await self._publish(
            run,
            RunEventKind.TOOL_FAILED,
            {
                "step_id": step.id,
                "tool": tool_name,
                "reason": (
                    "Tool execution is not connected "
                    "to the runtime yet."
                ),
            },
        )

    async def _generate_response(
        self,
        *,
        version: AgentVersion,
        prompt: str,
        plan: ExecutionPlan,
        execution_context: list[dict[str, Any]],
        history: list[dict[str, str]],
    ) -> str:
        """Generate the final response from the completed run context."""

        messages = [
            ChatMessage(
                role=ChatRole.SYSTEM,
                content=version.system_prompt or "",
            )
        ]

        for item in history:
            role = (
                ChatRole.ASSISTANT
                if item.get("role") == "assistant"
                else ChatRole.USER
            )

            content = item.get(
                "content",
                "",
            ).strip()

            if content:
                messages.append(
                    ChatMessage(
                        role=role,
                        content=content,
                    )
                )

        messages.append(
            ChatMessage(
                role=ChatRole.USER,
                content=(
                    f"Original task:\n{prompt}\n\n"
                    f"Execution plan:\n"
                    f"{plan.model_dump_json()}\n\n"
                    f"Execution results:\n"
                    f"{execution_context}\n\n"
                    "Produce the final useful response to the user."
                ),
            )
        )

        response = await llm_service.achat(
            messages,
            self._architect._provider,
            model=version.model,
            temperature=version.temperature,
            max_tokens=version.max_tokens,
        )

        return response.content

    async def _evaluate(
        self,
        *,
        run: Run,
        version: AgentVersion,
        prompt: str,
        plan: ExecutionPlan,
        execution_context: list[dict[str, Any]],
    ) -> None:
        """Evaluate the completed run."""

        try:
            evaluation = await self._evaluator.evaluate(
                run=run,
                agent_version=version,
                task=prompt,
                plan=plan,
                execution_context={
                    "steps": execution_context,
                },
            )

            run.metadata = {
                **run.metadata,
                "evaluation": evaluation.model_dump(),
            }

            await self._publish(
                run,
                RunEventKind.EVALUATION_COMPLETED,
                evaluation.model_dump(),
            )

        except EvaluationError as exc:
            run.metadata = {
                **run.metadata,
                "evaluation_error": str(exc),
            }

    async def _publish_step(
        self,
        run: Run,
        text: str,
    ) -> None:
        """Publish a frontend-friendly progress step."""

        await self._publish(
            run,
            RunEventKind.RUN_STARTED,
            {
                "step": text,
            },
        )

    async def _publish(
        self,
        run: Run,
        kind: RunEventKind,
        data: dict[str, Any],
    ) -> None:
        """Publish an event with a monotonically increasing sequence."""

        sequence = int(
            run.metadata.get(
                "_event_sequence",
                0,
            )
        )

        run.metadata["_event_sequence"] = (
            sequence + 1
        )

        await event_bus.publish(
            RunEvent(
                run_id=run.id,
                kind=kind,
                sequence=sequence,
                data=data,
                timestamp=self._now().isoformat(),
                parent_run_id=run.parent_run_id,
            )
        )

    def _resolve_agent(
        self,
        *,
        prompt: str,
        agent_id: UUID | None,
    ) -> tuple[Agent, AgentVersion]:
        """Resolve an existing agent or create a new one."""

        if agent_id is not None:
            agent = agent_store.get_agent(
                agent_id
            )

            if agent is None:
                raise AgentRuntimeError(
                    f"Agent '{agent_id}' was not found."
                )

            version = agent_store.get_agent_version(
                agent
            )

            if version is None:
                raise AgentRuntimeError(
                    f"Agent '{agent_id}' has no active version."
                )

            return agent, version

        return self._create_agent_for_prompt(
            prompt
        )

    def _create_agent_for_prompt(
        self,
        prompt: str,
    ) -> tuple[Agent, AgentVersion]:
        """Create a temporary/default agent for a new chat."""

        words = [
            word
            for word in prompt.split()
            if word.strip()
        ]

        name = " ".join(
            words[:6]
        ).strip()

        if len(name) < 3:
            name = "New Accord Agent"

        name = name[:255]

        slug = self._slug(name)

        original_slug = slug
        counter = 2

        while any(
            existing.slug == slug
            for existing in agent_store.list_agents()
        ):
            slug = (
                f"{original_slug}-{counter}"
            )
            counter += 1

        llm_provider = self._architect._provider

        agent = Agent(
            name=name,
            slug=slug,
            description=prompt[:500],
            status=AgentStatus.ACTIVE,
        )

        version = AgentVersion(
            agent_id=agent.id,
            version="1.0.0",
            model=llm_provider.model,
            temperature=0.2,
            max_tokens=1024,
            system_prompt=(
                "You are an Accord agent created for the user's "
                "requested objective. Follow the user's task carefully."
            ),
            created_by="agent-runtime",
        )

        agent.current_version_id = version.id

        agent_store.save_agent(agent)
        agent_store.save_version(version)

        return agent, version

    @staticmethod
    def _slug(
        value: str,
    ) -> str:
        return (
            value.lower()
            .strip()
            .replace(" ", "-")
            .replace("_", "-")
        )[:120]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)


runtime = AgentRuntime()