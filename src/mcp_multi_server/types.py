"""Type definitions for MCP multi-server client."""

from typing import Optional

from mcp.types import ListPromptsResult, ListResourcesResult, ListResourceTemplatesResult, ListToolsResult
from pydantic import BaseModel


class ServerCapabilities(BaseModel):
    """Capabilities discovered from an MCP server.

    This class stores all the capabilities (tools, resources, prompts, templates)
    that were discovered during server initialization. It's used internally to
    track what each server can do and to aggregate capabilities across all servers.

    Attributes:
        name: The unique identifier for the server.
        tools: List of tools provided by the server, if any.
        resources: List of resources provided by the server, if any.
        resource_templates: List of resource templates provided by the server, if any.
        prompts: List of prompts provided by the server, if any.

    Note:
        All capability fields (tools, resources, etc.) are optional because:
        - A server may not implement all capability types
        - Capability discovery may fail for some types while succeeding for others
        - Empty capability lists are represented as None rather than empty lists
    """

    name: str
    tools: Optional[ListToolsResult] = None
    resources: Optional[ListResourcesResult] = None
    resource_templates: Optional[ListResourceTemplatesResult] = None
    prompts: Optional[ListPromptsResult] = None
