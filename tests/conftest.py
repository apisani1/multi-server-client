"""Pytest configuration and fixtures for testing MultiServerClient."""

import json
import sys
import tempfile
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from pydantic import AnyUrl

from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextContent,
    TextResourceContents,
    Tool,
)


THIS_DIR = Path(__file__).parent
TESTS_DIR_PARENT = (THIS_DIR / "..").resolve()

# Ensure that `from tests ...` import statements work within the tests/ dir
sys.path.insert(0, str(TESTS_DIR_PARENT))

# Add src directory to path to ensure package can be importe
src_dir = TESTS_DIR_PARENT / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))


# ============================================================================
# Sample Test Data
# ============================================================================


@pytest.fixture
def sample_tools() -> List[Tool]:
    """Sample MCP tools for testing."""
    return [
        Tool(
            name="get_weather",
            description="Get weather for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "units": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        ),
        Tool(
            name="calculate",
            description="Perform calculations",
            inputSchema={
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        ),
    ]


@pytest.fixture
def sample_resources() -> List[Resource]:
    """Sample MCP resources for testing."""
    return [
        Resource(
            uri=AnyUrl("inventory://overview"),
            name="Inventory Overview",
            description="Overview of inventory system",
            mimeType="text/plain",
        ),
        Resource(
            uri=AnyUrl("inventory://items"),
            name="All Items",
            description="List of all inventory items",
            mimeType="application/json",
        ),
    ]


@pytest.fixture
def sample_resource_templates() -> List[ResourceTemplate]:
    """Sample MCP resource templates for testing."""
    return [
        ResourceTemplate(
            uriTemplate="inventory://item/{item_id}",
            name="Item by ID",
            description="Get item by UUID",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="inventory://category/{category}",
            name="Items by Category",
            description="Get items in a category",
            mimeType="application/json",
        ),
    ]


@pytest.fixture
def sample_prompts() -> List[Prompt]:
    """Sample MCP prompts for testing."""
    return [
        Prompt(
            name="write_report",
            description="Generate a report",
            arguments=[
                PromptArgument(name="topic", description="Report topic", required=True),
                PromptArgument(name="length", description="Report length", required=False),
            ],
        ),
        Prompt(name="roleplay", description="Start a roleplay scenario", arguments=[]),
    ]


# ============================================================================
# Mock Server Fixtures
# ============================================================================


@pytest.fixture
def mock_tool_server(sample_tools: List[Tool]) -> MagicMock:
    """Mock MCP server that provides tools."""
    server = MagicMock()

    # Mock list_tools
    server.list_tools = AsyncMock(return_value=ListToolsResult(tools=sample_tools))

    # Mock call_tool
    async def mock_call_tool(name: str, arguments: Dict[str, Any], **kwargs: Any) -> CallToolResult:
        # Accept but ignore read_timeout_seconds and progress_callback
        if name == "get_weather":
            return CallToolResult(
                content=[TextContent(type="text", text=f"Weather in {arguments.get('location')}: Sunny, 72°F")],
                isError=False,
            )
        elif name == "calculate":
            return CallToolResult(
                content=[TextContent(type="text", text=f"Result: {eval(arguments.get('expression', '0'))}")],
                isError=False,
            )
        else:
            return CallToolResult(content=[TextContent(type="text", text=f"Unknown tool: {name}")], isError=True)

    server.call_tool = AsyncMock(side_effect=mock_call_tool)

    # Mock list_resources/prompts (empty for tool server)
    server.list_resources = AsyncMock(return_value=ListResourcesResult(resources=[]))
    server.list_resource_templates = AsyncMock(return_value=ListResourceTemplatesResult(resourceTemplates=[]))
    server.list_prompts = AsyncMock(return_value=ListPromptsResult(prompts=[]))

    return server


@pytest.fixture
def mock_resource_server(
    sample_resources: List[Resource], sample_resource_templates: List[ResourceTemplate]
) -> MagicMock:
    """Mock MCP server that provides resources."""
    server = MagicMock()

    # Mock list_resources
    server.list_resources = AsyncMock(return_value=ListResourcesResult(resources=sample_resources))

    # Mock list_resource_templates
    server.list_resource_templates = AsyncMock(
        return_value=ListResourceTemplatesResult(resourceTemplates=sample_resource_templates)
    )

    # Mock read_resource
    async def mock_read_resource(uri: Any) -> ReadResourceResult:
        # Convert AnyUrl to string if needed
        uri_str = str(uri)

        if uri_str == "inventory://overview":
            return ReadResourceResult(
                contents=[
                    TextResourceContents(uri=uri, mimeType="text/plain", text="Inventory Overview: 100 items total")
                ]
            )
        elif uri_str == "inventory://items":
            return ReadResourceResult(
                contents=[
                    TextResourceContents(uri=uri, mimeType="application/json", text='[{"id": 1, "name": "Item 1"}]')
                ]
            )
        elif uri_str.startswith("inventory://item/"):
            item_id = uri_str.split("/")[-1]
            return ReadResourceResult(
                contents=[
                    TextResourceContents(
                        uri=uri, mimeType="application/json", text=f'{{"id": "{item_id}", "name": "Sample Item"}}'
                    )
                ]
            )
        else:
            raise ValueError(f"Unknown resource URI: {uri_str}")

    server.read_resource = AsyncMock(side_effect=mock_read_resource)

    # Mock list_tools/prompts (empty for resource server)
    server.list_tools = AsyncMock(return_value=ListToolsResult(tools=[]))
    server.list_prompts = AsyncMock(return_value=ListPromptsResult(prompts=[]))

    return server


@pytest.fixture
def mock_prompt_server(sample_prompts: List[Prompt]) -> MagicMock:
    """Mock MCP server that provides prompts."""
    server = MagicMock()

    # Mock list_prompts
    server.list_prompts = AsyncMock(return_value=ListPromptsResult(prompts=sample_prompts))

    # Mock get_prompt
    async def mock_get_prompt(name: str, arguments: Optional[Dict[str, str]] = None, **kwargs: Any) -> GetPromptResult:
        # Handle arguments being None
        args = arguments or {}

        if name == "write_report":
            topic = args.get("topic", "General")
            length = args.get("length", "medium")
            return GetPromptResult(
                messages=[
                    PromptMessage(
                        role="user", content=TextContent(type="text", text=f"Write a {length} report about {topic}")
                    )
                ]
            )
        elif name == "roleplay":
            return GetPromptResult(
                messages=[
                    PromptMessage(
                        role="user", content=TextContent(type="text", text="Let's start a roleplay scenario")
                    )
                ]
            )
        else:
            raise ValueError(f"Unknown prompt: {name}")

    server.get_prompt = AsyncMock(side_effect=mock_get_prompt)

    # Mock list_tools/resources (empty for prompt server)
    server.list_tools = AsyncMock(return_value=ListToolsResult(tools=[]))
    server.list_resources = AsyncMock(return_value=ListResourcesResult(resources=[]))
    server.list_resource_templates = AsyncMock(return_value=ListResourceTemplatesResult(resourceTemplates=[]))

    return server


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def sample_config_dict() -> Dict[str, Any]:
    """Sample configuration dictionary."""
    return {
        "mcpServers": {
            "tool_server": {"command": "python", "args": ["-m", "test.tool_server"]},
            "resource_server": {"command": "python", "args": ["-m", "test.resource_server"]},
            "prompt_server": {"command": "python", "args": ["-m", "test.prompt_server"]},
        }
    }


@pytest.fixture
def sample_config_file(sample_config_dict: Dict[str, Any]) -> Generator[Path, None, None]:
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_config_dict, f)
        path = Path(f.name)

    yield path

    # Cleanup
    if path.exists():
        path.unlink()


@pytest.fixture
def minimal_config_dict() -> Dict[str, Any]:
    """Minimal configuration with single server."""
    return {"mcpServers": {"test_server": {"command": "python", "args": ["-m", "test_server"]}}}


@pytest.fixture
def empty_config_dict() -> Dict[str, Any]:
    """Empty configuration (no servers)."""
    return {"mcpServers": {}}
