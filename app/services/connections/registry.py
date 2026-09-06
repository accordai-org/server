"""Connection-provider registry."""

from __future__ import annotations

from app.schemas.connection import ConnectionKind
from app.services.connections.api import APIConnectionProvider
from app.services.connections.base import (
    ConnectionConfigurationError,
    ConnectionProvider,
)
from app.services.connections.builtin import BuiltinConnectionProvider
from app.services.connections.mcp import MCPConnectionProvider


class ConnectionRegistry:
    """Resolve a connection into its provider implementation."""

    def __init__(self) -> None:
        self._providers: dict[str, ConnectionProvider] = {
            ConnectionKind.API.value: APIConnectionProvider(),
            ConnectionKind.BUILTIN.value: BuiltinConnectionProvider(),
            ConnectionKind.MCP.value: MCPConnectionProvider(),
        }

    def get(
        self,
        kind: ConnectionKind | str,
    ) -> ConnectionProvider:
        key = (
            kind.value
            if isinstance(kind, ConnectionKind)
            else kind
        )

        provider = self._providers.get(key)

        if provider is None:
            raise ConnectionConfigurationError(
                f"Unsupported connection kind: '{key}'."
            )

        return provider

    async def close(self) -> None:
        for provider in self._providers.values():
            await provider.close()