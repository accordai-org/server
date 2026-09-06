"""In-process agent run event bus."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from app.schemas.run_event import RunEvent


class RunEventBus:
    """Publish/subscribe bus for live agent run events."""

    def __init__(self) -> None:
        self._subscribers: dict[
            str,
            set[asyncio.Queue[RunEvent | None]],
        ] = defaultdict(set)

    async def publish(
        self,
        event: RunEvent,
    ) -> None:
        subscribers = list(
            self._subscribers.get(
                str(event.run_id),
                set(),
            )
        )

        for queue in subscribers:
            await queue.put(event)

    async def subscribe(
        self,
        run_id,
    ) -> AsyncIterator[RunEvent]:
        queue: asyncio.Queue[
            RunEvent | None
        ] = asyncio.Queue()

        key = str(run_id)

        self._subscribers[key].add(queue)

        try:
            while True:
                event = await queue.get()

                if event is None:
                    break

                yield event

        finally:
            self._subscribers[key].discard(queue)

            if not self._subscribers[key]:
                self._subscribers.pop(key, None)

    async def close_run(
        self,
        run_id,
    ) -> None:
        subscribers = list(
            self._subscribers.get(
                str(run_id),
                set(),
            )
        )

        for queue in subscribers:
            await queue.put(None)


event_bus = RunEventBus()