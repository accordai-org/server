"""In-process event bus for live agent runs."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from uuid import UUID

from app.schemas.run_event import RunEvent


class RunEventBus:
    """Publish live events to all subscribers for a run."""

    def __init__(self) -> None:
        self._subscribers: dict[
            UUID,
            set[asyncio.Queue[RunEvent | None]],
        ] = defaultdict(set)

    def subscribe(
        self,
        run_id: UUID,
    ) -> asyncio.Queue[RunEvent | None]:
        queue: asyncio.Queue[RunEvent | None] = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(
        self,
        run_id: UUID,
        queue: asyncio.Queue[RunEvent | None],
    ) -> None:
        subscribers = self._subscribers.get(run_id)

        if not subscribers:
            return

        subscribers.discard(queue)

        if not subscribers:
            self._subscribers.pop(run_id, None)

    async def publish(
        self,
        event: RunEvent,
    ) -> None:
        for queue in list(
            self._subscribers.get(event.run_id, set())
        ):
            await queue.put(event)

    async def close_run(
        self,
        run_id: UUID,
    ) -> None:
        for queue in list(
            self._subscribers.get(run_id, set())
        ):
            await queue.put(None)

    async def events(
        self,
        run_id: UUID,
        queue: asyncio.Queue[RunEvent | None],
    ) -> AsyncIterator[RunEvent]:
        try:
            while True:
                event = await queue.get()

                if event is None:
                    break

                yield event
        finally:
            self.unsubscribe(run_id, queue)


event_bus = RunEventBus()