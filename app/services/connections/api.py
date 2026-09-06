"""API connection provider."""

from app.schemas.connection import Connection, ConnectionKind
from app.schemas.tool import Tool
from app.services.connections.base import (
    ConnectionConfigurationError,
    ConnectionProvider,
)


class APIConnectionProvider(ConnectionProvider):
    """Resolves declared tools backed by an API connection."""

    @property
    def kind(self) -> str:
        return ConnectionKind.API.value

    async def discover_tools(
        self,
        connection: Connection,
    ) -> list[Tool]:
        if connection.kind is not ConnectionKind.API:
            raise ConnectionConfigurationError(
                f"Connection '{connection.id}' is not an API connection."
            )

        definitions = connection.metadata.get("tools", [])

        if not isinstance(definitions, list):
            raise ConnectionConfigurationError(
                f"API connection '{connection.name}' has invalid tool metadata."
            )

        return [
            Tool.model_validate(tool)
            for tool in definitions
        ]