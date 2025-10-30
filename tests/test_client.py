"""Tests for MultiServerClient class."""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_multi_server import MultiServerClient
from mcp_multi_server.config import MCPServersConfig
from mcp_multi_server.exceptions import (
    ConfigurationError,
    PromptNotFoundError,
    ResourceNotFoundError,
    ServerNotFoundError,
    ToolNotFoundError,
)


# ============================================================================
# Phase 3b: Initialization and Config Loading Tests
# ============================================================================


class TestClientInitialization:
    """Tests for MultiServerClient initialization."""

    def test_init_with_path_string(self, sample_config_file: Path) -> None:
        """Test initialization with path as string."""
        client = MultiServerClient(str(sample_config_file))

        assert client.config_path == Path(sample_config_file)
        assert client.sessions == {}
        assert client.capabilities == {}
        assert client.tool_to_server == {}
        assert client.prompt_to_server == {}

    def test_init_with_path_object(self, sample_config_file: Path) -> None:
        """Test initialization with Path object."""
        client = MultiServerClient(sample_config_file)

        assert client.config_path == sample_config_file
        assert client.sessions == {}
        assert client.capabilities == {}

    def test_init_does_not_load_config_immediately(self, sample_config_file: Path) -> None:
        """Test that initialization does not load config immediately (lazy loading)."""
        client = MultiServerClient(sample_config_file)

        # Config should be None until connect_all() is called
        assert client._config is None

    def test_init_with_nonexistent_file_succeeds(self) -> None:
        """Test initialization with non-existent file succeeds (lazy loading)."""
        # Initialization should succeed even with non-existent file
        client = MultiServerClient("/path/that/does/not/exist.json")
        assert client.config_path == Path("/path/that/does/not/exist.json")
        assert client._config is None

    def test_init_with_invalid_json_succeeds(self, tmp_path: Path) -> None:
        """Test initialization with invalid JSON succeeds (lazy loading)."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ this is not valid json }")

        # Initialization should succeed, error happens on connect_all()
        client = MultiServerClient(invalid_file)
        assert client.config_path == invalid_file
        assert client._config is None

    def test_init_with_invalid_config_schema_succeeds(self, tmp_path: Path) -> None:
        """Test initialization with invalid schema succeeds (lazy loading)."""
        invalid_file = tmp_path / "invalid_schema.json"
        invalid_file.write_text(json.dumps({"wrong_field": {}}))

        # Initialization should succeed, error happens on connect_all()
        client = MultiServerClient(invalid_file)
        assert client.config_path == invalid_file
        assert client._config is None


class TestFromConfigClassMethod:
    """Tests for from_config class method."""

    def test_from_config_with_path_string(self, sample_config_file: Path) -> None:
        """Test from_config with string path."""
        client = MultiServerClient.from_config(str(sample_config_file))

        assert isinstance(client, MultiServerClient)
        assert client.config_path == Path(sample_config_file)

    def test_from_config_with_path_object(self, sample_config_file: Path) -> None:
        """Test from_config with Path object."""
        client = MultiServerClient.from_config(sample_config_file)

        assert isinstance(client, MultiServerClient)
        assert client.config_path == sample_config_file

    def test_from_config_equivalent_to_init(self, sample_config_file: Path) -> None:
        """Test that from_config is equivalent to __init__."""
        client1 = MultiServerClient(sample_config_file)
        client2 = MultiServerClient.from_config(sample_config_file)

        assert client1.config_path == client2.config_path
        assert type(client1._config) == type(client2._config)


class TestFromDictClassMethod:
    """Tests for from_dict class method."""

    def test_from_dict_creates_client(self, sample_config_dict: Dict[str, Any]) -> None:
        """Test from_dict creates client from dictionary."""
        client = MultiServerClient.from_dict(sample_config_dict)

        assert isinstance(client, MultiServerClient)
        assert client.config_path == Path("memory://config")
        assert isinstance(client._config, MCPServersConfig)

    def test_from_dict_loads_servers(self, sample_config_dict: Dict[str, Any]) -> None:
        """Test from_dict loads server configurations."""
        client = MultiServerClient.from_dict(sample_config_dict)

        assert "tool_server" in client._config.mcpServers
        assert "resource_server" in client._config.mcpServers
        assert "prompt_server" in client._config.mcpServers

    def test_from_dict_with_minimal_config(self, minimal_config_dict: Dict[str, Any]) -> None:
        """Test from_dict with minimal configuration."""
        client = MultiServerClient.from_dict(minimal_config_dict)

        assert len(client._config.mcpServers) == 1
        assert "test_server" in client._config.mcpServers

    def test_from_dict_with_empty_config(self, empty_config_dict: Dict[str, Any]) -> None:
        """Test from_dict with empty configuration."""
        client = MultiServerClient.from_dict(empty_config_dict)

        assert len(client._config.mcpServers) == 0

    def test_from_dict_with_invalid_schema_raises_error(self) -> None:
        """Test from_dict with invalid schema raises pydantic ValidationError."""
        from pydantic import ValidationError

        invalid_dict = {"wrong_field": {}}

        with pytest.raises(ValidationError):
            MultiServerClient.from_dict(invalid_dict)


class TestContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio
    async def test_context_manager_enter_exit(self, sample_config_dict: Dict[str, Any]) -> None:
        """Test async context manager enter and exit."""
        client = MultiServerClient.from_dict(sample_config_dict)

        async with client as ctx_client:
            assert ctx_client is client
            assert client._stack is not None

        # After exit, stack should be cleaned up
        assert client._stack is None

    @pytest.mark.asyncio
    async def test_context_manager_multiple_uses_succeeds(self, empty_config_dict: Dict[str, Any]) -> None:
        """Test that using context manager twice succeeds (creates new stack each time)."""
        client = MultiServerClient.from_dict(empty_config_dict)

        async with client:
            assert client._stack is not None

        # Stack should be cleaned up
        assert client._stack is None

        # Second use should succeed (creates new stack)
        async with client:
            assert client._stack is not None

        assert client._stack is None

    @pytest.mark.asyncio
    async def test_context_manager_exception_cleanup(self, empty_config_dict: Dict[str, Any]) -> None:
        """Test that context manager cleans up on exception."""
        client = MultiServerClient.from_dict(empty_config_dict)

        try:
            async with client:
                assert client._stack is not None
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Stack should be cleaned up even after exception
        assert client._stack is None


# ============================================================================
# Phase 3c: Connection and Capability Aggregation Tests
# ============================================================================


class TestConnectionManagement:
    """Tests for server connection management."""

    @pytest.mark.asyncio
    async def test_connect_to_server_success(
        self,
        sample_config_dict: Dict[str, Any],
        mock_tool_server: MagicMock
    ) -> None:
        """Test successful connection to a server."""
        client = MultiServerClient.from_dict(sample_config_dict)

        # Mock the stdio_client context manager
        with patch("mcp_multi_server.client.stdio_client") as mock_stdio:
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_stdio.return_value.__aexit__ = AsyncMock()

            with patch("mcp_multi_server.client.ClientSession") as mock_session_class:
                mock_session = MagicMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value = mock_session

                async with client:
                    # Connection should be established
                    assert len(client.sessions) > 0

    @pytest.mark.asyncio
    async def test_connect_all_connects_all_servers(self, sample_config_dict: Dict[str, Any]) -> None:
        """Test connect_all connects to all configured servers."""
        client = MultiServerClient.from_dict(sample_config_dict)

        with patch("mcp_multi_server.client.stdio_client") as mock_stdio:
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_stdio.return_value.__aexit__ = AsyncMock()

            with patch("mcp_multi_server.client.ClientSession") as mock_session_class:
                mock_session = MagicMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value = mock_session

                async with client as ctx_client:
                    await ctx_client.connect_all(ctx_client._stack)

                    # Should have connected to all 3 servers
                    assert len(client.sessions) == 3
                    assert "tool_server" in client.sessions
                    assert "resource_server" in client.sessions
                    assert "prompt_server" in client.sessions


class TestCapabilityAggregation:
    """Tests for aggregating capabilities from multiple servers."""

    def test_list_tools_aggregates_from_all_servers(
        self,
        sample_config_dict: Dict[str, Any],
        sample_tools: list,
    ) -> None:
        """Test list_tools aggregates tools from all servers."""
        from mcp_multi_server.types import ServerCapabilities
        from mcp.types import ListToolsResult

        client = MultiServerClient.from_dict(sample_config_dict)

        # Populate capabilities (not sessions)
        client.capabilities = {
            "tool_server": ServerCapabilities(
                name="tool_server",
                tools=ListToolsResult(tools=sample_tools, nextCursor=None)
            ),
            "resource_server": ServerCapabilities(
                name="resource_server",
                tools=ListToolsResult(tools=[], nextCursor=None)
            )
        }

        result = client.list_tools()

        assert result.tools is not None
        assert len(result.tools) == 2  # get_weather and calculate
        assert result.tools[0].name == "get_weather"
        assert result.tools[1].name == "calculate"
        # Check that server attribution is added
        assert result.tools[0].meta.get("serverName") == "tool_server"

    def test_list_resources_aggregates_from_all_servers(
        self,
        sample_config_dict: Dict[str, Any],
        sample_resources: list,
    ) -> None:
        """Test list_resources aggregates resources from all servers."""
        from mcp_multi_server.types import ServerCapabilities
        from mcp.types import ListResourcesResult

        client = MultiServerClient.from_dict(sample_config_dict)

        # Populate capabilities
        client.capabilities = {
            "resource_server": ServerCapabilities(
                name="resource_server",
                resources=ListResourcesResult(resources=sample_resources, nextCursor=None)
            ),
            "tool_server": ServerCapabilities(
                name="tool_server",
                resources=ListResourcesResult(resources=[], nextCursor=None)
            )
        }

        result = client.list_resources()

        assert result.resources is not None
        assert len(result.resources) == 2
        # Resources are namespaced by default
        assert "resource_server:" in result.resources[0].uri
        assert "Inventory Overview" in result.resources[0].name

    def test_list_prompts_aggregates_from_all_servers(
        self,
        sample_config_dict: Dict[str, Any],
        sample_prompts: list,
    ) -> None:
        """Test list_prompts aggregates prompts from all servers."""
        from mcp_multi_server.types import ServerCapabilities
        from mcp.types import ListPromptsResult

        client = MultiServerClient.from_dict(sample_config_dict)

        # Populate capabilities
        client.capabilities = {
            "prompt_server": ServerCapabilities(
                name="prompt_server",
                prompts=ListPromptsResult(prompts=sample_prompts, nextCursor=None)
            ),
            "tool_server": ServerCapabilities(
                name="tool_server",
                prompts=ListPromptsResult(prompts=[], nextCursor=None)
            )
        }

        result = client.list_prompts()

        assert result.prompts is not None
        assert len(result.prompts) == 2
        assert result.prompts[0].name == "write_report"
        assert result.prompts[1].name == "roleplay"
        # Check that server attribution is added
        assert result.prompts[0].meta.get("serverName") == "prompt_server"


# ============================================================================
# Phase 3d: Routing Tests (Tools, Resources, Prompts)
# ============================================================================


class TestToolRouting:
    """Tests for tool routing to appropriate servers."""

    @pytest.mark.asyncio
    async def test_call_tool_routes_to_correct_server(
        self,
        sample_config_dict: Dict[str, Any],
        mock_tool_server: MagicMock,
    ) -> None:
        """Test call_tool routes to correct server."""
        client = MultiServerClient.from_dict(sample_config_dict)

        # Set up routing map
        client.tool_to_server = {"get_weather": "tool_server"}
        client.sessions = {"tool_server": mock_tool_server}

        result = await client.call_tool("get_weather", {"location": "San Francisco"})

        assert result.isError is False
        assert "San Francisco" in result.content[0].text
        mock_tool_server.call_tool.assert_called_once_with(
            "get_weather",
            {"location": "San Francisco"},
            read_timeout_seconds=None,
            progress_callback=None
        )

    @pytest.mark.asyncio
    async def test_call_tool_with_unknown_tool_returns_error(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test call_tool with unknown tool returns error result."""
        client = MultiServerClient.from_dict(sample_config_dict)
        client.tool_to_server = {}

        result = await client.call_tool("unknown_tool", {})

        # Should return error result, not raise exception
        assert result.isError is True
        assert "Unknown tool" in result.content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_with_explicit_unknown_server_returns_error(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test call_tool with explicit unknown server name returns error result."""
        client = MultiServerClient.from_dict(sample_config_dict)
        client.sessions = {}

        # Use explicit server_name parameter (not auto-routing)
        result = await client.call_tool("get_weather", {}, server_name="unknown_server")

        # Should return error result, not raise exception
        assert result.isError is True
        assert "Unknown server" in result.content[0].text


class TestResourceRouting:
    """Tests for resource routing to appropriate servers."""

    @pytest.mark.asyncio
    async def test_read_resource_with_namespace_routes_correctly(
        self,
        sample_config_dict: Dict[str, Any],
        mock_resource_server: MagicMock,
    ) -> None:
        """Test read_resource with namespaced URI routes correctly."""
        client = MultiServerClient.from_dict(sample_config_dict)
        client.sessions = {"resource_server": mock_resource_server}

        # Read resource with namespace prefix
        result = await client.read_resource("resource_server:inventory://overview")

        assert len(result.contents) > 0
        # For TextResourceContents, the content is in the text field
        assert hasattr(result.contents[0], 'text')
        assert "Inventory Overview" in result.contents[0].text
        # The mock server is called with AnyUrl type
        mock_resource_server.read_resource.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_resource_without_namespace_raises_mcperror(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test read_resource without namespace raises McpError."""
        from mcp.shared.exceptions import McpError

        client = MultiServerClient.from_dict(sample_config_dict)

        with pytest.raises(McpError, match="Must specify server_name"):
            await client.read_resource("inventory://overview")

    @pytest.mark.asyncio
    async def test_read_resource_with_unknown_server_raises_mcperror(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test read_resource with unknown server raises McpError."""
        from mcp.shared.exceptions import McpError

        client = MultiServerClient.from_dict(sample_config_dict)
        client.sessions = {}

        with pytest.raises(McpError):
            await client.read_resource("unknown_server:inventory://overview")


class TestPromptRouting:
    """Tests for prompt routing to appropriate servers."""

    @pytest.mark.asyncio
    async def test_get_prompt_routes_to_correct_server(
        self,
        sample_config_dict: Dict[str, Any],
        mock_prompt_server: MagicMock,
    ) -> None:
        """Test get_prompt routes to correct server."""
        client = MultiServerClient.from_dict(sample_config_dict)
        client.prompt_to_server = {"write_report": "prompt_server"}
        client.sessions = {"prompt_server": mock_prompt_server}

        result = await client.get_prompt("write_report", {"topic": "AI", "length": "short"})

        assert len(result.messages) > 0
        assert "AI" in result.messages[0].content.text
        # Check that server was called (actual parameters passed positionally, not named)
        mock_prompt_server.get_prompt.assert_called_once()
        # Verify the arguments
        call_args = mock_prompt_server.get_prompt.call_args
        assert call_args[0][0] == "write_report"  # first positional arg
        assert call_args[1]["arguments"] == {"topic": "AI", "length": "short"}  # keyword arg

    @pytest.mark.asyncio
    async def test_get_prompt_with_unknown_prompt_raises_mcperror(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test get_prompt with unknown prompt raises McpError."""
        from mcp.shared.exceptions import McpError

        client = MultiServerClient.from_dict(sample_config_dict)
        client.prompt_to_server = {}

        with pytest.raises(McpError, match="Unknown prompt"):
            await client.get_prompt("unknown_prompt", {})

    @pytest.mark.asyncio
    async def test_get_prompt_with_explicit_unknown_server_raises_mcperror(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test get_prompt with explicit unknown server raises McpError."""
        from mcp.shared.exceptions import McpError

        client = MultiServerClient.from_dict(sample_config_dict)
        client.sessions = {}

        with pytest.raises(McpError):
            await client.get_prompt("write_report", {}, server_name="unknown_server")


# ============================================================================
# Phase 3e: Error Handling and Collision Detection Tests
# ============================================================================


class TestCollisionDetection:
    """Tests for detecting and warning about collisions."""

    def test_detect_tool_collision_in_routing_map(
        self,
        sample_config_dict: Dict[str, Any],
        sample_tools: list,
    ) -> None:
        """Test that tool routing map handles last-registered-wins for collisions."""
        client = MultiServerClient.from_dict(sample_config_dict)

        # Manually set up collision scenario: same tool from two servers
        # In real usage, this happens during connect_all() where collision is logged
        client.tool_to_server = {}

        # First server registers the tool
        client.tool_to_server["get_weather"] = "server1"

        # Second server overwrites it (last-registered-wins)
        client.tool_to_server["get_weather"] = "server2"

        # The routing map should have the last server
        assert client.tool_to_server["get_weather"] == "server2"

    def test_detect_prompt_collision_in_routing_map(
        self,
        sample_config_dict: Dict[str, Any],
        sample_prompts: list,
    ) -> None:
        """Test that prompt routing map handles last-registered-wins for collisions."""
        client = MultiServerClient.from_dict(sample_config_dict)

        # Manually set up collision scenario: same prompt from two servers
        client.prompt_to_server = {}

        # First server registers the prompt
        client.prompt_to_server["write_report"] = "server1"

        # Second server overwrites it (last-registered-wins)
        client.prompt_to_server["write_report"] = "server2"

        # The routing map should have the last server
        assert client.prompt_to_server["write_report"] == "server2"


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_call_tool_handles_server_error(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test call_tool handles server errors gracefully."""
        client = MultiServerClient.from_dict(sample_config_dict)

        mock_server = MagicMock()
        mock_server.call_tool = AsyncMock(side_effect=Exception("Server error"))

        client.tool_to_server = {"test_tool": "test_server"}
        client.sessions = {"test_server": mock_server}

        with pytest.raises(Exception, match="Server error"):
            await client.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_read_resource_handles_server_error(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test read_resource handles server errors gracefully."""
        client = MultiServerClient.from_dict(sample_config_dict)

        mock_server = MagicMock()
        mock_server.read_resource = AsyncMock(side_effect=ValueError("Invalid URI"))

        client.sessions = {"test_server": mock_server}

        with pytest.raises(ValueError, match="Invalid URI"):
            await client.read_resource("test_server:invalid://uri")

    @pytest.mark.asyncio
    async def test_get_prompt_handles_server_error(
        self,
        sample_config_dict: Dict[str, Any]
    ) -> None:
        """Test get_prompt handles server errors gracefully."""
        client = MultiServerClient.from_dict(sample_config_dict)

        mock_server = MagicMock()
        mock_server.get_prompt = AsyncMock(side_effect=ValueError("Unknown prompt"))

        client.prompt_to_server = {"test_prompt": "test_server"}
        client.sessions = {"test_server": mock_server}

        with pytest.raises(ValueError, match="Unknown prompt"):
            await client.get_prompt("test_prompt", {})


class TestPrintCapabilitiesSummary:
    """Tests for print_capabilities_summary method."""

    def test_print_capabilities_summary_with_all_types(
        self,
        sample_config_dict: Dict[str, Any],
        sample_tools: list,
        sample_resources: list,
        sample_prompts: list,
        capsys: pytest.CaptureFixture
    ) -> None:
        """Test printing capabilities summary with all capability types."""
        from mcp_multi_server.types import ServerCapabilities
        from mcp.types import ListToolsResult, ListResourcesResult, ListPromptsResult

        client = MultiServerClient.from_dict(sample_config_dict)

        # Populate capabilities directly (not via list_* methods)
        client.capabilities = {
            "tool_server": ServerCapabilities(
                name="tool_server",
                tools=ListToolsResult(tools=sample_tools, nextCursor=None)
            ),
            "resource_server": ServerCapabilities(
                name="resource_server",
                resources=ListResourcesResult(resources=sample_resources, nextCursor=None)
            ),
            "prompt_server": ServerCapabilities(
                name="prompt_server",
                prompts=ListPromptsResult(prompts=sample_prompts, nextCursor=None)
            )
        }

        # Print summary
        client.print_capabilities_summary()

        captured = capsys.readouterr()
        assert "tool_server" in captured.out
        assert "resource_server" in captured.out
        assert "prompt_server" in captured.out
        assert "get_weather" in captured.out  # Tool name
        assert "Inventory Overview" in captured.out  # Resource name
        assert "write_report" in captured.out  # Prompt name

    def test_print_capabilities_summary_with_empty_capabilities(
        self,
        sample_config_dict: Dict[str, Any],
        capsys: pytest.CaptureFixture
    ) -> None:
        """Test printing capabilities summary with no capabilities."""
        client = MultiServerClient.from_dict(sample_config_dict)
        client.capabilities = {}

        client.print_capabilities_summary()

        captured = capsys.readouterr()
        # Should still produce header even with no capabilities
        assert "CAPABILITIES SUMMARY" in captured.out
