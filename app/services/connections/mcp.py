"""MCP connection provider."""

from __future__ import annotations

from mcp import Client

from app.schemas.connection import Connection, ConnectionKind
from app.schemas.enums import ToolKind
from app.schemas.tool import Tool
from app.services.connections.base import (
    ConnectionConfigurationError,
    ConnectionError,
    ConnectionProvider,
)


class MCPConnectionProvider(ConnectionProvider):
    """Discover and interact with MCP servers."""

    @property
    def kind(self) -> str:
        return ConnectionKind.MCP.value

    async def discover_tools(
        self,
        connection: Connection,
    ) -> list[Tool]:
        if connection.kind is not ConnectionKind.MCP:
            raise ConnectionConfigurationError(
                f"Connection '{connection.id}' is not an MCP connection."
            )

        if not connection.endpoint:
            raise ConnectionConfigurationError(
                f"MCP connection '{connection.name}' has no endpoint."
            )

        try:
            async with Client(connection.endpoint) as client:
                result = await client.list_tools()
        except Exception as exc:
            raise ConnectionError(
                f"Failed to discover MCP tools for "
                f"'{connection.name}': {exc}"
            ) from exc

        return [
            Tool(
                name=tool.title or tool.name,
                slug=self._slug(tool.name),
                connection_id=connection.id,
                description=tool.description,
                kind=ToolKind.MCP,
                version="1.0.0",
                input_schema=tool.input_schema,
                output_schema=None,
                auth_config={
                    "connection_id": str(connection.id),
                },
                is_active=(
                    connection.status.value == "active"
                ),
            )
            for tool in result.tools
        ]

    @staticmethod
    def _slug(name: str) -> str:
        """Create a stable Tool slug from an MCP tool name."""

        slug = name.strip().lower()

        for character in ("_", ".", "/", " "):
            slug = slug.replace(character, "-")

        return slug