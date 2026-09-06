"""Tool and AgentToolBinding domain models.

Tools form a versioned catalog. They attach to an agent version via an
explicit AgentToolBinding join (per chosen design), which carries the
pinned tool version plus per-version config overrides.
"""

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.agent_version import SEMVER_PATTERN
from app.schemas.common import DomainBase
from app.schemas.enums import ToolKind

from uuid import UUID


class Tool(DomainBase):
    """One versioned tool in the catalog."""

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    connection_id: UUID | None = Field(
      default=None,
      description="Connection that exposes this tool, when applicable."
    )
    description: str | None = Field(default=None)
    kind: ToolKind = Field(default=ToolKind.FUNCTION)
    version: str = Field(pattern=SEMVER_PATTERN, description="Tool SemVer, e.g. '2.0.1'.")
    input_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema for tool inputs."
    )
    output_schema: dict[str, Any] | None = Field(default=None)
    auth_config: dict[str, Any] | None = Field(
        default=None, description="Opaque auth metadata. Never store raw secrets."
    )
    is_active: bool = Field(default=True)


class AgentToolBinding(DomainBase):
    """Explicit join: which tools an agent version enables and how."""

    agent_id: UUID = Field(description="Owning Agent.id (denormalized for queries).")
    agent_version_id: UUID = Field(description="AgentVersion.id this binding belongs to.")
    tool_id: UUID = Field(description="Tool.id being bound.")
    tool_version: str | None = Field(
        default=None,
        pattern=SEMVER_PATTERN,
        description="Pinned tool SemVer. Null = latest active.",
    )
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = Field(default=True)
    order: int | None = Field(default=None, ge=0)
