"""Memory persistence abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.memory import Memory


class MemoryRepository(ABC):
    """Persistence interface for memories."""

    @abstractmethod
    async def save(self, memory: Memory) -> Memory:
        """Persist a memory and return it."""

    @abstractmethod
    async def get(self, memory_id: UUID) -> Memory | None:
        """Retrieve a memory by ID."""

    @abstractmethod
    async def search(
        self,
        *,
        agent_id: UUID,
        query: str | None = None,
        subject_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve relevant memories."""

    @abstractmethod
    async def delete(self, memory_id: UUID) -> None:
        """Delete a memory."""

    async def close(self) -> None:
        """Release repository resources."""