"""Built-in connection provider."""

from app.schemas.connection import Connection, ConnectionKind
from app.schemas.tool import Tool
from app.services.connections.base import (
    ConnectionConfigurationError,
    ConnectionProvider,
)


class BuiltinConnectionProvider(ConnectionProvider):
    """Resolves tools implemented natively by Accord."""

    @property
    def kind(self) -> str:
        return ConnectionKind.BUILTIN.value

    async def discover_tools(
        self,
        connection: Connection,
    ) -> list[Tool]:
        if connection.kind is not ConnectionKind.BUILTIN:
            raise ConnectionConfigurationError(
                f"Connection '{connection.id}' is not a builtin connection."
            )

        tools = connection.metadata.get("tools", [])

        if not isinstance(tools, list):
            raise ConnectionConfigurationError(
                f"Builtin connection '{connection.name}' has invalid tool metadata."
            )

        return [
            Tool.model_validate(tool)
            for tool in tools
        ]