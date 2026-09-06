"""Agent execution-plan domain models.

The Architect produces a provider-neutral plan describing what an agent
should do. The plan contains intent and executable parameters, not hidden
chain-of-thought.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanStepKind(str, Enum):
    """Supported types of agent actions."""

    PREPARE = "prepare"
    EXECUTE = "execute"
    TOOL = "tool"
    RESPOND = "respond"


class PlanStep(BaseModel):
    """One actionable step in an execution plan."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1,
        max_length=100,
        description="Stable identifier within the plan.",
    )
    kind: PlanStepKind
    instruction: str = Field(
        min_length=1,
        description="What this step should accomplish.",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of steps that must complete first.",
    )
    tool_name: str | None = Field(
        default=None,
        description="Requested tool capability, resolved later by Tool Discovery.",
    )
    command: str | None = Field(
        default=None,
        description="Command to execute when kind == execute.",
    )
    args: list[str] = Field(
        default_factory=list,
        description="Arguments for command execution.",
    )
    expected_output: str | None = Field(
        default=None,
        description="What successful completion of the step should produce.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """Complete plan produced by the Agent Architect."""

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(
        min_length=1,
        description="Normalized objective the plan is intended to achieve.",
    )
    steps: list[PlanStep] = Field(
        min_length=1,
        description="Ordered or dependency-linked actionable steps.",
    )
    final_response: str = Field(
        min_length=1,
        description="Instructions for how the final user-facing response should be produced.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)