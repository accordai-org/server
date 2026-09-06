"""Memory management service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.schemas.memory import Memory
from app.schemas.enums import MemoryKind, MemoryScope
from app.services.memory.in_memory import InMemoryMemoryRepository
from app.services.memory.repository import MemoryRepository


class MemoryService:
    """Store and retrieve agent memories."""

    def __init__(
        self,
        repository: MemoryRepository | None = None,
    ) -> None:
        self._repository = (
            repository
            or InMemoryMemoryRepository()
        )

    async def remember(
        self,
        *,
        agent_id: UUID,
        content: str,
        key: str,
        kind: MemoryKind = MemoryKind.FACT,
        scope: MemoryScope = MemoryScope.AGENT,
        run_id: UUID | None = None,
        subject_id: str | None = None,
        importance: float = 0.5,
        expires_at=None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        memory = Memory(
            agent_id=agent_id,
            run_id=run_id,
            subject_id=subject_id,
            scope=scope,
            kind=kind,
            key=key,
            content=content,
            importance=importance,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        return await self._repository.save(memory)

    async def recall(
        self,
        *,
        agent_id: UUID,
        query: str | None = None,
        subject_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        memories = await self._repository.search(
            agent_id=agent_id,
            query=query,
            subject_id=subject_id,
            limit=limit,
        )

        now = datetime.now(timezone.utc)

        return [
            memory
            for memory in memories
            if (
                memory.expires_at is None
                or memory.expires_at > now
            )
        ]

    async def forget(
        self,
        memory_id: UUID,
    ) -> None:
        await self._repository.delete(memory_id)

    async def close(self) -> None:
        await self._repository.close()