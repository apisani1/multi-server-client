"""Configuration models for MCP multi-server client."""

from typing import Dict, List

from pydantic import BaseModel


class ServerConfig(BaseModel):
    """Configuration for a single MCP server.

    Attributes:
        command: The executable command to start the server (e.g., "python", "node").
        args: Command-line arguments to pass to the server executable.

    Examples:
        >>> config = ServerConfig(
        ...     command="python",
        ...     args=["-m", "my_mcp_server.tool_server"]
        ... )
    """

    command: str
    args: List[str]


class MCPServersConfig(BaseModel):
    """Configuration for all MCP servers.

    Attributes:
        mcpServers: Dictionary mapping server names to their configurations.
                   Server names are used as identifiers throughout the client.

    Examples:
        >>> config = MCPServersConfig(mcpServers={
        ...     "tool_server": ServerConfig(
        ...         command="python",
        ...         args=["-m", "my_mcp_server.tool_server"]
        ...     ),
        ...     "resource_server": ServerConfig(
        ...         command="python",
        ...         args=["-m", "my_mcp_server.resource_server"]
        ...     )
        ... })
    """

    mcpServers: Dict[str, ServerConfig]
