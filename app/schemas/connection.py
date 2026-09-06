"""Connection domain models.

A connection represents an authenticated/configured relationship between
Accord and an external capability source. Connections expose tools; they
are not themselves tools.

Secrets must never be stored directly in these models.
"""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import DomainBase


class ConnectionKind(str, Enum):
    """How Accord reaches the connected capability source."""

    BUILTIN = "builtin"
    API = "api"
    MCP = "mcp"


class ConnectionStatus(str, Enum):
    """Lifecycle/health state of a connection."""

    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class Connection(DomainBase):
    """A configured connection to an external or native capability source."""

    name: str = Field(min_length=1, max_length=255)
    provider: str = Field(
        min_length=1,
        max_length=100,
        description="Stable provider identifier, e.g. gmail, google-drive, ramp.",
    )
    kind: ConnectionKind
    status: ConnectionStatus = Field(default=ConnectionStatus.ACTIVE)

    endpoint: str | None = Field(
        default=None,
        description="Endpoint used by API/MCP connections.",
    )

    credential_ref: str | None = Field(
        default=None,
        description="Reference to stored credentials. Never store raw secrets here.",
    )

    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentConnectionBinding(DomainBase):
    """Explicitly grants an agent version access to a connection."""

    agent_id: UUID = Field(description="Owning Agent.id.")
    agent_version_id: UUID = Field(description="AgentVersion.id.")
    connection_id: UUID = Field(description="Connection.id.")
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = Field(default=True)
    order: int | None = Field(default=None, ge=0)