"""Memory domain model.

Memories are scoped (agent / run / user / global) and typed by kind.
Vector-ready: optional ``embedding`` stored alongside content; no
dimension check yet (defer to the future vector store).
"""

from typing import Any, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.common import DomainBase
from app.schemas.enums import MemoryKind, MemoryScope


class Memory(DomainBase):
    """One retrievable memory record."""

    agent_id: UUID | None = Field(
        default=None,
        description="Owning agent. Null only when scope == global.",
    )
    run_id: UUID | None = Field(
        default=None, description="Source run, if any."
    )
    subject_id: str | None = Field(
        default=None, description="User subject when scope == user."
    )
    scope: MemoryScope = Field(default=MemoryScope.AGENT)
    kind: MemoryKind = Field(default=MemoryKind.FACT)
    key: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, description="Memory payload (text).")
    embedding: list[float] | None = Field(default=None)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    expires_at: AwareDatetime | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_scope(self) -> Self:
        if self.scope == MemoryScope.RUN and self.run_id is None:
            raise ValueError("scope 'run' requires run_id")
        if self.scope == MemoryScope.USER and not self.subject_id:
            raise ValueError("scope 'user' requires subject_id")
        if self.scope == MemoryScope.GLOBAL and self.agent_id is not None:
            raise ValueError("scope 'global' must not set agent_id")
        if self.scope in (
            MemoryScope.AGENT,
            MemoryScope.RUN,
            MemoryScope.USER,
        ) and self.agent_id is None:
            raise ValueError(f"scope '{self.scope.value}' requires agent_id")
        return self
