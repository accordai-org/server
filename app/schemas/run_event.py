"""Agent run event models."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunEventKind(str, Enum):
    RUN_STARTED = "run.started"
    PLAN_CREATED = "plan.created"

    EXECUTION_STARTED = "execution.started"
    EXECUTION_STDOUT = "execution.stdout"
    EXECUTION_STDERR = "execution.stderr"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"

    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"

    EVALUATION_COMPLETED = "evaluation.completed"

    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


class RunEvent(BaseModel):
    """One event emitted during an agent run."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    kind: RunEventKind
    sequence: int = Field(ge=0)

    data: dict[str, Any] = Field(
        default_factory=dict
    )

    timestamp: str

    parent_run_id: UUID | None = None