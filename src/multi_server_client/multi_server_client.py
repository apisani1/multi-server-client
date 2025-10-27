import json
import logging
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

from pydantic import (
    AnyUrl,
    BaseModel,
)

from mcp import (
    ClientSession,
    StdioServerParameters,
)
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp.shared.session import ProgressFnT
from mcp.types import (
    CallToolResult,
    ErrorData,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)


# Configure logger for this module
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)-60s %(filename)s:%(lineno)d",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    command: str
    args: List[str]


class MCPServersConfig(BaseModel):
    """Configuration for all MCP servers."""

    mcpServers: Dict[str, ServerConfig]


class ServerCapabilities(BaseModel):
    """Capabilities discovered from an MCP server."""

    name: str
    tools: Optional[ListToolsResult] = None
    resources: Optional[ListResourcesResult] = None
    resource_templates: Optional[ListResourceTemplatesResult] = None
    prompts: Optional[ListPromptsResult] = None


class MultiServerClient:
    """Manages multiple MCP server connections for a MCP host.

    This class handles:
    - Connecting to multiple MCP servers
    - Discovering and aggregating capabilities (tools, resources, prompts)
    - Routing tool, prompt and resource calls to the correct server
    - Managing session lifecycles with AsyncExitStack
    """

    def __init__(self, config_path: str = "mcp_servers.json"):
        """Initialize the multi-server client.

        Args:
            config_path: Path to the JSON configuration file containing server definitions.
        """
        self.config_path = Path(config_path)
        self.sessions: Dict[str, ClientSession] = {}
        self.capabilities: Dict[str, ServerCapabilities] = {}
        self.tool_to_server: Dict[str, str] = {}
        self.prompt_to_server: Dict[str, str] = {}

    def load_config(self) -> MCPServersConfig:
        """Load server configuration from JSON file.

        Returns:
            Parsed configuration object.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            json.JSONDecodeError: If config file is invalid JSON.
            pydantic.ValidationError: If config data doesn't match schema.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, encoding="utf-8") as f:
            config_data = json.load(f)

        return MCPServersConfig.model_validate(config_data)

    async def connect_all(self, stack: AsyncExitStack) -> None:
        """Connect to all configured MCP servers and discover their capabilities.

        Args:
            stack: AsyncExitStack for managing async context managers.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            json.JSONDecodeError: If config file is invalid JSON.
            pydantic.ValidationError: If config data doesn't match schema.

        Note:
            Individual server connection failures are caught and logged as warnings.
            The method will continue connecting to remaining servers if one fails.
        """
        config = self.load_config()

        logger.info("Connecting to %d MCP servers...", len(config.mcpServers))

        for server_name, server_config in config.mcpServers.items():
            try:
                await self._connect_server(stack, server_name, server_config)
            except Exception as e:
                logger.warning("Failed to connect to %s: %s", server_name, e)
                continue

        logger.info("Successfully connected to %d server(s)", len(self.sessions))

    async def _connect_server(self, stack: AsyncExitStack, server_name: str, server_config: ServerConfig) -> None:
        """Connect to a single MCP server and discover its capabilities.

        Args:
            stack: AsyncExitStack for managing async context managers.
            server_name: Name identifier for this server.
            server_config: Server connection parameters.

        Raises:
            FileNotFoundError: If server command executable doesn't exist.
            PermissionError: If lacking permission to execute server command.
            OSError: If server process cannot be started.
            McpError: If MCP protocol initialization fails.
            TimeoutError: If connection or initialization times out.
            pydantic.ValidationError: If server parameters are invalid.

        Note:
            Failures during capability discovery (tools, resources, prompts, templates)
            are caught and logged as warnings. The server will still be registered with
            partial capabilities if connection and initialization succeed.
        """
        logger.info("[%s] Connecting...", server_name)

        # Create server parameters
        params = StdioServerParameters(command=server_config.command, args=server_config.args)

        # Connect to server
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))

        # Initialize session
        await session.initialize()
        self.sessions[server_name] = session

        # Discover capabilities
        capabilities = ServerCapabilities(name=server_name)

        # Get tools
        try:
            tools_result = await session.list_tools()
            capabilities.tools = tools_result
            logger.info("[%s] Found %d tool(s)", server_name, len(tools_result.tools))

            # Map tools to server
            for tool in tools_result.tools:
                if tool.name in self.tool_to_server:
                    existing_server = self.tool_to_server[tool.name]
                    logger.warning(
                        "Tool '%s' collision detected! Already provided by '%s', now overridden by '%s'",
                        tool.name,
                        existing_server,
                        server_name,
                    )
                self.tool_to_server[tool.name] = server_name

        except Exception as e:
            logger.warning("[%s] No tools available: %s", server_name, e)

        # Get resources
        try:
            resources_result = await session.list_resources()
            capabilities.resources = resources_result
            logger.info("[%s] Found %d resource(s)", server_name, len(resources_result.resources))
        except Exception as e:
            logger.warning("[%s] No resources available: %s", server_name, e)

        # Get resource templates
        try:
            templates_result = await session.list_resource_templates()
            capabilities.resource_templates = templates_result
            logger.info("[%s] Found %d resource template(s)", server_name, len(templates_result.resourceTemplates))
        except Exception as e:
            logger.warning("[%s] No resource templates available: %s", server_name, e)

        # Get prompts
        try:
            prompts_result = await session.list_prompts()
            capabilities.prompts = prompts_result
            logger.info("[%s] Found %d prompt(s)", server_name, len(prompts_result.prompts))

            # Map prompts to server
            for prompt in prompts_result.prompts:
                if prompt.name in self.prompt_to_server:
                    existing_server = self.prompt_to_server[prompt.name]
                    logger.warning(
                        "Prompt '%s' collision detected! Already provided by '%s', now overridden by '%s'",
                        prompt.name,
                        existing_server,
                        server_name,
                    )
                self.prompt_to_server[prompt.name] = server_name

        except Exception as e:
            logger.warning("[%s] No prompts available: %s", server_name, e)

        self.capabilities[server_name] = capabilities

    def list_tools(self, cursor: Optional[str] = None) -> ListToolsResult:
        """Get combined list of all tools from all servers.

        This method mimics the MCP ClientSession.list_tools() signature but aggregates
        tools from all connected servers. Server attribution is included in each tool's
        meta field.

        Args:
            cursor: Optional pagination cursor. Not supported for multi-server aggregation,
                must be None if provided.

        Returns:
            ListToolsResult containing all tools from all servers with server_name in meta.
            The nextCursor field is always None (pagination not supported).

        Raises:
            ValueError: If cursor is not None (pagination not supported).

        Example:
            result = client.list_tools()
            for tool in result.tools:
                server = tool.meta.get("serverName") if tool.meta else None
                print(f"{tool.name} from {server}")
        """
        if cursor is not None:
            raise ValueError("Pagination not supported for multi-server aggregation")

        all_tools: List[Tool] = []
        for server_name, capabilities in self.capabilities.items():
            if capabilities.tools:
                for tool in capabilities.tools.tools:
                    # Add server name to tool's meta field
                    existing_meta = tool.meta or {}
                    tool_with_meta = tool.model_copy(update={"meta": {**existing_meta, "serverName": server_name}})
                    all_tools.append(tool_with_meta)

        return ListToolsResult(tools=all_tools, nextCursor=None)

    def list_prompts(self, cursor: Optional[str] = None) -> ListPromptsResult:
        """Get combined list of all prompts from all servers.

        This method mimics the MCP ClientSession.list_prompts() signature but aggregates
        prompts from all connected servers. Server attribution is included in each prompt's
        meta field.

        Args:
            cursor: Optional pagination cursor. Not supported for multi-server aggregation,
                must be None if provided.

        Returns:
            ListPromptsResult containing all prompts from all servers with server_name in meta.
            The nextCursor field is always None (pagination not supported).

        Raises:
            ValueError: If cursor is not None (pagination not supported).

        Example:
            result = client.list_prompts()
            for prompt in result.prompts:
                server = prompt.meta.get("serverName") if prompt.meta else None
                print(f"{prompt.name} from {server}")
        """
        if cursor is not None:
            raise ValueError("Pagination not supported for multi-server aggregation")

        all_prompts: List[Prompt] = []
        for server_name, capabilities in self.capabilities.items():
            if capabilities.prompts:
                for prompt in capabilities.prompts.prompts:
                    # Add server name to prompt's meta field
                    existing_meta = prompt.meta or {}
                    prompt_with_meta = prompt.model_copy(update={"meta": {**existing_meta, "serverName": server_name}})
                    all_prompts.append(prompt_with_meta)

        return ListPromptsResult(prompts=all_prompts, nextCursor=None)

    def list_resources(self, cursor: Optional[str] = None, use_namespace: bool = True) -> ListResourcesResult:
        """Get combined list of all resources from all servers.

        This method mimics the MCP ClientSession.list_resources() signature but aggregates
        resources from all connected servers. Resources are returned with namespaced URIs
        (server:uri format) for auto-routing, and server attribution is included in each
        resource's meta field.

        Args:
            cursor: Optional pagination cursor. Not supported for multi-server aggregation,
                must be None if provided.
            use_namespace: Whether to namespace the URIs with the server name.

        Returns:
            ListResourcesResult containing all resources from all servers with:
            - Namespaced URIs in format "server_name:original_uri" for auto-routing
            - server_name in meta field for explicit server identification
            The nextCursor field is always None (pagination not supported).

        Raises:
            ValueError: If cursor is not None (pagination not supported).

        Example:
            result = client.list_resources()
            for resource in result.resources:
                server = resource.meta.get("serverName") if resource.meta else None
                # URI is already namespaced: "filesystem:file:///path"
                content = await client.read_resource(resource.uri)
        """
        if cursor is not None:
            raise ValueError("Pagination not supported for multi-server aggregation")

        all_resources: List[Resource] = []
        for server_name, capabilities in self.capabilities.items():
            if capabilities.resources:
                for resource in capabilities.resources.resources:
                    # Add server name to meta and namespace the URI
                    existing_meta = resource.meta or {}
                    resource_with_meta = resource.model_copy(
                        update={
                            "uri": f"{server_name}:{resource.uri}" if use_namespace else resource.uri,
                            "meta": {**existing_meta, "serverName": server_name},
                        }
                    )
                    all_resources.append(resource_with_meta)

        return ListResourcesResult(resources=all_resources, nextCursor=None)

    def list_resource_templates(
        self, cursor: Optional[str] = None, use_namespace: bool = True
    ) -> ListResourceTemplatesResult:
        """Get combined list of all resource templates from all servers.

        This method mimics the MCP ClientSession.list_resource_templates() signature but
        aggregates resource templates from all connected servers. Templates are returned
        with namespaced URI templates (server:template format) for auto-routing, and server
        attribution is included in each template's meta field.

        Args:
            cursor: Optional pagination cursor. Not supported for multi-server aggregation,
                must be None if provided.
            use_namespace: Whether to namespace the URI templates with the server name.

        Returns:
            ListResourceTemplatesResult containing all templates from all servers with:
            - Namespaced URI templates in format "server_name:original_template"
            - server_name in meta field for explicit server identification
            The nextCursor field is always None (pagination not supported).

        Raises:
            ValueError: If cursor is not None (pagination not supported).

        Example:
            result = client.list_resource_templates()
            for template in result.resourceTemplates:
                server = template.meta.get("serverName") if template.meta else None
                # URI template is already namespaced: "filesystem:file:///{path}"
                uri = template.uriTemplate.replace("{path}", "example.txt")
                content = await client.read_resource(uri)
        """
        if cursor is not None:
            raise ValueError("Pagination not supported for multi-server aggregation")

        all_templates: List[ResourceTemplate] = []
        for server_name, capabilities in self.capabilities.items():
            if capabilities.resource_templates:
                for template in capabilities.resource_templates.resourceTemplates:
                    # Add server name to meta and namespace the URI template
                    existing_meta = template.meta or {}
                    template_with_meta = template.model_copy(
                        update={
                            "uriTemplate": (
                                f"{server_name}:{template.uriTemplate}" if use_namespace else template.uriTemplate
                            ),
                            "meta": {**existing_meta, "serverName": server_name},
                        }
                    )
                    all_templates.append(template_with_meta)

        return ListResourceTemplatesResult(resourceTemplates=all_templates, nextCursor=None)

    def _create_error_result(self, error_message: str) -> CallToolResult:
        """Create a CallToolResult indicating an error.

        Args:
            error_message: The error message to include in the result.

        Returns:
            CallToolResult with isError=True and the error message in content.
        """
        return CallToolResult(
            content=[TextContent(type="text", text=error_message)],
            isError=True,
        )

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        read_timeout_seconds: Optional[timedelta] = None,
        progress_callback: Optional[ProgressFnT] = None,
        server_name: Optional[str] = None,
    ) -> CallToolResult:
        """Route a tool call to the appropriate server.

        Args:
            name: Name of the tool to call.
            arguments: Arguments to pass to the tool.
            read_timeout_seconds: Optional timeout for reading the tool result.
            progress_callback: Optional callback for progress notifications.
            server_name: Optional server name to explicitly specify which server to use.
                If not provided, the server will be automatically determined from the tool name.

        Returns:
            Result from the tool execution. If the tool name is not found or routing fails,
            returns a CallToolResult with isError=True containing an error message.

        Raises:
            McpError: If the tool execution fails or times out (protocol-level errors).
            RuntimeError: If tool result validation fails (invalid structured content or schema).

        Note:
            Routing errors (unknown tool, unknown server) are returned as error results
            (isError=True) rather than raising exceptions, following MCP protocol conventions.
            Protocol-level errors from the underlying session are propagated as exceptions.
        """
        if server_name is None:
            # Auto-route using the tool mapping
            server_name = self.tool_to_server.get(name)
            if not server_name:
                return self._create_error_result(f"Unknown tool: {name}")
        else:
            # Validate the explicitly provided server name
            if server_name not in self.sessions:
                return self._create_error_result(f"Unknown server: {server_name}")

            # Validate that the tool exists on the specified server
            server_capabilities = self.capabilities[server_name]
            if server_capabilities.tools is None:
                return self._create_error_result(f"Server '{server_name}' has no tools")

            if name not in {tool.name for tool in server_capabilities.tools.tools}:
                return self._create_error_result(f"Tool '{name}' not found in server '{server_name}'")

        session = self.sessions[server_name]
        return await session.call_tool(
            name,
            arguments,
            read_timeout_seconds=read_timeout_seconds,
            progress_callback=progress_callback,
        )

    async def read_resource(self, uri: Union[str, AnyUrl], server_name: Optional[str] = None) -> ReadResourceResult:
        """Read a resource with optional auto-routing via namespaced URIs.

        Args:
            uri: Resource URI. Can be namespaced as "server:uri" for auto-routing.
                 URIs from list_resources() are already namespaced for convenience.
                 Accepts both str and AnyUrl types for MCP library compatibility.
            server_name: Optional explicit server name. If provided, ignores any namespace
                        in the URI and uses this server directly.

        Returns:
            Resource content.

        Raises:
            McpError: If server name is not found, URI is not namespaced when server_name
                     is not provided, or if the resource read fails or times out.

        Examples:
            # Auto-routing with namespaced URI (from list_resources())
            resources = client.list_resources().resources
            result = await client.read_resource(resources[0].uri)

            # Explicit server (ignores namespace if present in URI)
            result = await client.read_resource("file:///path", server_name="filesystem")

            # Manual namespacing
            result = await client.read_resource("filesystem:file:///path")

        Note:
            Raises McpError for both routing errors and protocol-level errors to align
            with MCP SDK behavior.
        """
        # Convert AnyUrl to string for processing
        uri_str = str(uri)
        actual_uri = uri_str

        if server_name is None:
            # Try to extract server from namespaced URI
            if ":" in uri_str:
                potential_server, potential_uri = uri_str.split(":", 1)
                if potential_server in self.sessions:
                    server_name = potential_server
                    actual_uri = potential_uri

            if server_name is None:
                raise McpError(
                    ErrorData(
                        code=-32601,
                        message="Must specify server_name or use namespaced URI format (server:uri)",
                    )
                )

        session = self.sessions.get(server_name)
        if not session:
            raise McpError(ErrorData(code=-32601, message=f"Unknown server: {server_name}"))

        return await session.read_resource(AnyUrl(actual_uri))

    async def get_prompt(
        self,
        name: str,
        arguments: Optional[Dict[str, str]] = None,
        server_name: Optional[str] = None,
    ) -> GetPromptResult:
        """Get a prompt by automatically routing to the appropriate server.

        Args:
            name: Name of the prompt to get.
            arguments: Optional arguments for the prompt.
            server_name: Optional server name to explicitly specify which server to use.
                If not provided, the server will be automatically determined from the prompt name.

        Returns:
            Prompt result.

        Raises:
            McpError: If prompt name is not found, server name is not found, or if the
                prompt retrieval fails or times out.

        Note:
            Raises McpError for both routing errors and protocol-level errors to align
            with MCP SDK behavior.
        """
        if server_name is None:
            # Auto-route using the prompt mapping
            server_name = self.prompt_to_server.get(name)
            if not server_name:
                raise McpError(ErrorData(code=-32601, message=f"Unknown prompt: {name}"))
        else:
            # Validate the explicitly provided server name
            if server_name not in self.sessions:
                raise McpError(ErrorData(code=-32601, message=f"Unknown server: {server_name}"))

            # Validate that the prompt exists on the specified server
            server_capabilities = self.capabilities[server_name]
            if server_capabilities.prompts is None:
                raise McpError(ErrorData(code=-32601, message=f"Server '{server_name}' has no prompts"))

            if name not in {prompt.name for prompt in server_capabilities.prompts.prompts}:
                raise McpError(ErrorData(code=-32601, message=f"Prompt '{name}' not found in server '{server_name}'"))

        session = self.sessions[server_name]
        return await session.get_prompt(name, arguments=arguments or {})

    def print_capabilities_summary(self) -> None:
        """Print a summary of all discovered capabilities."""
        print("\n" + "=" * 80)
        print("CAPABILITIES SUMMARY")
        print("=" * 80)

        for server_name, caps in self.capabilities.items():
            print(f"\n[{server_name}]")

            if caps.tools and caps.tools.tools:
                print(f"  Tools ({len(caps.tools.tools)}):")
                for tool in caps.tools.tools:
                    print(f"    - {tool.name}: {tool.description}")

            if caps.resources and caps.resources.resources:
                print(f"  Resources ({len(caps.resources.resources)}):")
                for resource in caps.resources.resources:
                    print(f"    - {resource.name}: {resource.uri}")

            if caps.resource_templates and caps.resource_templates.resourceTemplates:
                print(f"  Resource Templates ({len(caps.resource_templates.resourceTemplates)}):")
                for template in caps.resource_templates.resourceTemplates:
                    print(f"    - {template.name}: {template.uriTemplate}")

            if caps.prompts and caps.prompts.prompts:
                print(f"  Prompts ({len(caps.prompts.prompts)}):")
                for prompt in caps.prompts.prompts:
                    print(f"    - {prompt.name}: {prompt.description}")

        print("\n" + "=" * 80 + "\n")
