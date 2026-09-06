"""Provider-neutral connection interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.connection import Connection
from app.schemas.tool import Tool


class ConnectionError(Exception):
    """Base error for connection providers."""


class ConnectionConfigurationError(ConnectionError):
    """Raised when a connection is incorrectly configured."""


class ConnectionProvider(ABC):
    """Interface implemented by every connection mechanism."""

    @property
    @abstractmethod
    def kind(self) -> str:
        """Return the connection kind."""

    @abstractmethod
    async def discover_tools(
        self,
        connection: Connection,
    ) -> list[Tool]:
        """Discover capabilities exposed by the connection."""

    async def close(self) -> None:
        """Release provider-level resources."""