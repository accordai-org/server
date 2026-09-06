"""EvaluationResult domain model.

An evaluation scores one (Agent, AgentVersion) pair — optionally tied to
a single Run, or suite-aggregate when run_id is None.
"""

from uuid import UUID

from pydantic import Field

from app.schemas.common import DomainBase


class EvaluationResult(DomainBase):
    """One evaluation outcome."""

    agent_id: UUID = Field(description="Evaluated Agent.id.")
    agent_version_id: UUID = Field(description="Evaluated AgentVersion.id.")
    run_id: UUID | None = Field(
        default=None, description="Source Run.id. Null = suite-aggregate score."
    )
    suite: str = Field(
        min_length=1, description="Eval suite / dataset name, e.g. 'support-v2'."
    )
    dataset_version: str | None = Field(default=None)
    metrics: dict[str, float] = Field(
        default_factory=dict, description="Named numeric metrics."
    )
    score: float | None = Field(default=None, description="Aggregate score, if any.")
    passed: bool | None = Field(default=None)
    evaluator: str = Field(
        default="code", description="Who evaluated, e.g. 'human', 'llm:gpt-4o', 'code'."
    )
    notes: str | None = Field(default=None)
