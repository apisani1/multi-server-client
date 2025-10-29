"""Custom exceptions for MCP multi-server client."""


class MultiServerClientError(Exception):
    """Base exception for all multi-server client errors.

    All custom exceptions in this module inherit from this base class,
    making it easy to catch all client-specific errors.
    """

    pass


class ConfigurationError(MultiServerClientError):
    """Raised when there's an error in server configuration.

    This includes issues like:
    - Missing or invalid configuration files
    - Malformed JSON in configuration
    - Invalid server parameters
    - Schema validation failures

    Examples:
        >>> raise ConfigurationError("Config file not found: mcp_servers.json")
        >>> raise ConfigurationError("Invalid server config: missing 'command' field")
    """

    pass


class ServerNotFoundError(MultiServerClientError):
    """Raised when attempting to interact with a server that doesn't exist.

    This occurs when:
    - Explicitly specifying a server name that wasn't configured
    - Attempting to use a server that failed to connect

    Examples:
        >>> raise ServerNotFoundError("Unknown server: my_server")
        >>> raise ServerNotFoundError("Server 'tool_server' is not connected")
    """

    pass


class ToolNotFoundError(MultiServerClientError):
    """Raised when attempting to call a tool that doesn't exist.

    This occurs when:
    - Calling a tool that no server provides
    - Calling a tool on a specific server that doesn't have it

    Examples:
        >>> raise ToolNotFoundError("Unknown tool: calculate_fibonacci")
        >>> raise ToolNotFoundError("Tool 'add_member' not found in server 'resource_server'")
    """

    pass


class PromptNotFoundError(MultiServerClientError):
    """Raised when attempting to retrieve a prompt that doesn't exist.

    This occurs when:
    - Requesting a prompt that no server provides
    - Requesting a prompt from a specific server that doesn't have it

    Examples:
        >>> raise PromptNotFoundError("Unknown prompt: write_code")
        >>> raise PromptNotFoundError("Prompt 'roleplay' not found in server 'tool_server'")
    """

    pass


class ResourceNotFoundError(MultiServerClientError):
    """Raised when attempting to read a resource that doesn't exist or is inaccessible.

    This occurs when:
    - Reading a resource with an invalid or non-existent URI
    - Reading a resource without proper server routing information
    - Accessing a resource that requires authentication

    Examples:
        >>> raise ResourceNotFoundError("Resource URI must be namespaced: server:uri")
        >>> raise ResourceNotFoundError("Resource not found: filesystem:file:///missing.txt")
    """

    pass
