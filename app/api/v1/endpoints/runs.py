"""Agent run streaming endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.events import event_bus


router = APIRouter(
    prefix="/runs",
    tags=["runs"],
)


@router.get(
    "/{run_id}/stream",
    summary="Stream agent run events",
)
async def stream_run(
    run_id: UUID,
) -> StreamingResponse:
    queue = event_bus.subscribe(run_id)

    async def event_generator():
        async for event in event_bus.events(
            run_id,
            queue,
        ):
            yield (
                f"id: {event.sequence}\n"
                f"event: {event.kind.value}\n"
                f"data: {event.model_dump_json()}\n\n"
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