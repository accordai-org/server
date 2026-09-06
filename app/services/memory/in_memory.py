"""In-memory memory repository.

Useful for development and unit tests until persistent storage is connected.
"""

from __future__ import annotations

from uuid import UUID

from app.schemas.memory import Memory
from app.services.memory.repository import MemoryRepository


class InMemoryMemoryRepository(MemoryRepository):
    """Simple in-process memory repository."""

    def __init__(self) -> None:
        self._memories: dict[UUID, Memory] = {}

    async def save(self, memory: Memory) -> Memory:
        self._memories[memory.id] = memory
        return memory

    async def get(self, memory_id: UUID) -> Memory | None:
        return self._memories.get(memory_id)

    async def search(
        self,
        *,
        agent_id: UUID,
        query: str | None = None,
        subject_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        candidates = [
            memory
            for memory in self._memories.values()
            if (
                memory.agent_id == agent_id
                and (
                    subject_id is None
                    or memory.subject_id == subject_id
                )
            )
        ]

        if query:
            terms = {
                term.lower()
                for term in query.split()
                if term.strip()
            }

            def score(memory: Memory) -> int:
                haystack = (
                    f"{memory.key} {memory.content}"
                ).lower()

                return sum(
                    1
                    for term in terms
                    if term in haystack
                )

            candidates.sort(
                key=lambda memory: (
                    score(memory),
                    memory.importance,
                    memory.updated_at,
                ),
                reverse=True,
            )
        else:
            candidates.sort(
                key=lambda memory: (
                    memory.importance,
                    memory.updated_at,
                ),
                reverse=True,
            )

        return candidates[:limit]

    async def delete(self, memory_id: UUID) -> None:
        self._memories.pop(memory_id, None)