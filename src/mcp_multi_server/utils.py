"""Utility functions for MCP multi-server client."""

import re
from typing import (
    Any,
    Dict,
    List,
)
from urllib.parse import quote

from mcp.types import Tool


def mcp_tools_to_openai_format(tools: List[Tool]) -> List[Dict[str, Any]]:
    """Convert MCP tools to OpenAI function calling format.

    This function transforms MCP tool definitions into the format expected by
    OpenAI's function calling API, enabling seamless integration between MCP
    servers and OpenAI language models.

    Args:
        tools: List of MCP Tool objects to convert.

    Returns:
        List of tool definitions in OpenAI format, where each tool is a dict with:
        - type: Always "function"
        - function: Dict containing name, description, and parameters (JSON schema)

    Examples:
        >>> from mcp.types import Tool
        >>> mcp_tools = [
        ...     Tool(
        ...         name="get_weather",
        ...         description="Get weather for a location",
        ...         inputSchema={"type": "object", "properties": {"location": {"type": "string"}}}
        ...     )
        ... ]
        >>> openai_tools = mcp_tools_to_openai_format(mcp_tools)
        >>> openai_tools[0]["function"]["name"]
        'get_weather'

    Note:
        The inputSchema from MCP tools is used directly as the parameters
        field in OpenAI format, as both follow JSON Schema specifications.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools
    ]


def format_namespace_uri(server_name: str, uri: str) -> str:
    """Format a URI with a server namespace prefix.

    Args:
        server_name: Name of the server providing the resource.
        uri: Original URI of the resource.

    Returns:
        Namespaced URI in the format "server_name:uri".

    Examples:
        >>> format_namespace_uri("filesystem", "file:///path/to/file.txt")
        'filesystem:file:///path/to/file.txt'
        >>> format_namespace_uri("db", "records://users/123")
        'db:records://users/123'

    Note:
        This function is used internally by the client to namespace resource URIs
        for auto-routing. Users typically don't need to call this directly.
    """
    return f"{server_name}:{uri}"


def parse_namespace_uri(namespaced_uri: str) -> tuple[str | None, str]:
    """Parse a namespaced URI to extract server name and original URI.

    Args:
        namespaced_uri: URI that may contain a server namespace prefix.

    Returns:
        Tuple of (server_name, uri). If no namespace is present, server_name is None
        and uri is the original input.

    Examples:
        >>> parse_namespace_uri("filesystem:file:///path/to/file.txt")
        ('filesystem', 'file:///path/to/file.txt')
        >>> parse_namespace_uri("file:///path/to/file.txt")
        (None, 'file:///path/to/file.txt')
        >>> parse_namespace_uri("db:records://users/123")
        ('db', 'records://users/123')

    Note:
        This function looks for the first colon to determine if a namespace exists.
        It does not validate that the extracted server name actually exists.
    """
    if ":" in namespaced_uri:
        parts = namespaced_uri.split(":", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None, namespaced_uri


def extract_template_variables(uri_template: str) -> List[str]:
    """Extract variable names from a URI template.

    URI templates use curly braces to denote variables that should be substituted.

    Args:
        uri_template: URI template string with variables in {variable} format.

    Returns:
        List of variable names found in the template (without braces).

    Examples:
        >>> extract_template_variables("file:///{path}/to/{filename}")
        ['path', 'filename']
        >>> extract_template_variables("users/{id}/posts/{post_id}")
        ['id', 'post_id']
        >>> extract_template_variables("no/variables/here")
        []
    """
    pattern = r"\{([^}]+)\}"
    return re.findall(pattern, uri_template)


def substitute_template_variables(uri_template: str, variables: Dict[str, str]) -> str:
    """Substitute variables in URI template with provided values.

    Variable values are URL-encoded to handle spaces and special characters properly.

    Args:
        uri_template: URI template string with variables in {variable} format.
        variables: Dictionary mapping variable names to their replacement values.

    Returns:
        URI with all variables replaced by their encoded values.

    Examples:
        >>> substitute_template_variables(
        ...     "file:///{path}/{filename}",
        ...     {"path": "my documents", "filename": "report.txt"}
        ... )
        'file:///my%20documents/report.txt'
        >>> substitute_template_variables(
        ...     "users/{id}",
        ...     {"id": "123"}
        ... )
        'users/123'

    Note:
        Values are URL-encoded using urllib.parse.quote with safe="" to ensure
        proper handling of special characters in URIs.
    """
    result = uri_template
    for var, value in variables.items():
        # URL encode the value to handle spaces and special characters
        encoded_value = quote(value, safe="")
        result = result.replace(f"{{{var}}}", encoded_value)
    return result
