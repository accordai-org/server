"""AgentVersion domain model.

Each row snapshots one SemVer release of an agent's config (prompt,
model, decoding params). Versions are mutable drafts (``updated_at``
tracked on DomainBase); enforce immutability later at the service/DB
layer if needed. Future DB unique constraint: (agent_id, version).
Tools attach via AgentToolBinding, not inline here.
"""

from uuid import UUID

from pydantic import Field

from app.schemas.common import DomainBase

SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"


class AgentVersion(DomainBase):
    """One versioned config snapshot for an Agent."""

    agent_id: UUID = Field(description="Parent Agent.id.")
    version: str = Field(
        pattern=SEMVER_PATTERN, description="SemVer string, e.g. '1.2.0'."
    )
    system_prompt: str | None = Field(default=None)
    model: str = Field(default="gpt-4o-mini", description="LLM model identifier.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0)
    parent_version_id: UUID | None = Field(
        default=None, description="Previous AgentVersion.id this was cloned from."
    )
    changelog: str | None = Field(default=None)
    created_by: str | None = Field(
        default=None, description="Creator subject (user id or service name)."
    )
