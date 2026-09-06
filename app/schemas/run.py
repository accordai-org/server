"""Run domain model (canonical name for executions/runs).

``Execution`` is a documented alias — use ``Run`` everywhere. A Run is
one end-to-end invocation of an (Agent, AgentVersion) pair.
"""

from typing import Any, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.schemas.common import DomainBase
from app.schemas.enums import RunStatus

TERMINAL_STATUSES = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    }
)


class RunUsage(BaseModel):
    """Token / latency / cost accounting for a run."""

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)


class RunError(BaseModel):
    """Failure detail; required when status == failed."""

    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable error message.")
    retryable: bool = Field(default=False)


class Run(DomainBase):
    """One execution of an agent version."""

    agent_id: UUID = Field(description="Owning Agent.id.")
    agent_version_id: UUID = Field(description="Executed AgentVersion.id.")
    status: RunStatus = Field(default=RunStatus.QUEUED)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = Field(default=None)
    usage: RunUsage | None = Field(default=None)
    error: RunError | None = Field(default=None)
    triggered_by: str | None = Field(default=None)
    parent_run_id: UUID | None = Field(
        default=None, description="Set for retries / sub-runs."
    )
    started_at: AwareDatetime | None = Field(default=None)
    ended_at: AwareDatetime | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_lifecycle(self) -> Self:
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at < self.started_at
        ):
            raise ValueError("ended_at must be >= started_at")
        if self.status in TERMINAL_STATUSES and self.ended_at is None:
            raise ValueError(f"status '{self.status.value}' requires ended_at")
        if self.status == RunStatus.FAILED and self.error is None:
            raise ValueError("status 'failed' requires error detail")
        return self


# Documented alias: the codebase standard is Run.
Execution = Run
