"""LearnedStrategy domain model.

Strategies distill what worked across runs/memories into reusable
guidance for an agent. Provenance is kept via source run/memory ids,
and adoption is tracked via promoted_in_version_id.
"""

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import DomainBase
from app.schemas.enums import StrategyStatus


class LearnedStrategy(DomainBase):
    """One learned strategy for an agent."""

    agent_id: UUID = Field(description="Owning Agent.id.")
    title: str = Field(min_length=1, max_length=255)
    strategy_text: str = Field(min_length=1, description="Actionable strategy content.")
    source_run_ids: list[UUID] = Field(
        default_factory=list, description="Runs this was distilled from."
    )
    source_memory_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: StrategyStatus = Field(default=StrategyStatus.CANDIDATE)
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Evidence justifying promotion."
    )
    promoted_in_version_id: UUID | None = Field(
        default=None, description="AgentVersion.id that adopted this strategy."
    )
