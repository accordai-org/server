"""Agent execution endpoints."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.agent.runtime import (
    AgentRuntimeError,
    runtime,
)
from app.services.events import event_bus
from app.schemas.run_event import RunEventKind


class AgentChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    agent_id: UUID | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    history: list[dict[str, str]] = Field(
        default_factory=list,
    )


router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


@router.post(
    "/chat",
    summary="Run an Accord agent",
)
async def agent_chat(
    body: AgentChatRequest,
) -> StreamingResponse:
    run = runtime.prepare_run(
        prompt=body.prompt,
        agent_id=body.agent_id,
        tools=body.tools,
        skills=body.skills,
        history=body.history,
    )

    queue = event_bus.subscribe(run.id)

    async def event_generator() -> AsyncIterator[str]:
        task = asyncio.create_task(
            runtime.execute_run(run)
        )

        try:
            async for event in event_bus.events(
                run.id,
                queue,
            ):
                if event.kind is RunEventKind.RUN_STARTED:
                    text = event.data.get("step")

                    if text:
                        yield (
                            "event: step\n"
                            f"data: {json.dumps({'text': text})}\n\n"
                        )

                elif event.kind is RunEventKind.PLAN_CREATED:
                    yield (
                        "event: step\n"
                        f"data: {json.dumps({'text': 'Plan ready. Preparing execution…'})}\n\n"
                    )

                elif event.kind is RunEventKind.EXECUTION_STARTED:
                    yield (
                        "event: step\n"
                        f"data: {json.dumps({'text': 'Testing your agent in sandbox…'})}\n\n"
                    )

                elif event.kind is RunEventKind.TOOL_STARTED:
                    tool = event.data.get("tool") or "connected tool"

                    yield (
                        "event: step\n"
                        f"data: {json.dumps({'text': f'Using {tool}…'})}\n\n"
                    )

                elif event.kind is RunEventKind.EVALUATION_COMPLETED:
                    yield (
                        "event: step\n"
                        f"data: {json.dumps({'text': 'Checking the result…'})}\n\n"
                    )

                elif event.kind is RunEventKind.RUN_COMPLETED:
                    content = event.data.get(
                        "content",
                        "",
                    )

                    for index in range(
                        0,
                        len(content),
                        120,
                    ):
                        yield (
                            "event: delta\n"
                            f"data: {json.dumps({'content': content[index:index + 120]})}\n\n"
                        )

                    yield (
                        "event: tools\n"
                        f"data: {json.dumps({'tools': body.tools})}\n\n"
                    )

                    yield (
                        "event: done\n"
                        f"data: {json.dumps({'run_id': str(run.id), 'agent_id': str(run.agent_id)})}\n\n"
                    )

                elif event.kind is RunEventKind.RUN_FAILED:
                    yield (
                        "event: error\n"
                        f"data: {json.dumps({'message': event.data.get('message', 'Agent run failed.')})}\n\n"
                    )

            try:
                await task
            except AgentRuntimeError:
                pass

        finally:
            if not task.done():
                task.cancel()

            event_bus.unsubscribe(
                run.id,
                queue,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )