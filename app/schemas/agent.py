"""Agent domain model.

An Agent is the long-lived identity (name/slug/status). Mutable config
lives on AgentVersion; Agent only tracks which version is current.
Relationship: Agent 1—N AgentVersion via ``AgentVersion.agent_id``.
"""

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import DomainBase
from app.schemas.enums import AgentStatus


class Agent(DomainBase):
    """Long-lived agent identity."""

    name: str = Field(min_length=1, max_length=255, description="Human-readable name.")
    slug: str = Field(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe unique slug, e.g. 'support-copilot'.",
    )
    description: str | None = Field(default=None, description="What this agent does.")
    owner_id: UUID | None = Field(
        default=None, description="Owner subject. No User model yet — nullable."
    )
    status: AgentStatus = Field(default=AgentStatus.DRAFT)
    current_version_id: UUID | None = Field(
        default=None,
        description="Points at AgentVersion.id once a first version exists.",
    )
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
