# MCP Multi-Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for managing connections to multiple [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers. This library provides a unified interface for discovering, aggregating, and routing capabilities (tools, resources, prompts) across multiple MCP servers.

## Features

- **Multi-Server Management**: Connect to and manage multiple MCP servers simultaneously
- **Automatic Capability Discovery**: Discover tools, resources, prompts, and templates from all connected servers
- **Intelligent Routing**: Automatically route tool calls, resource reads, and prompt retrievals to the correct server
- **Namespace Support**: Use namespaced URIs for unambiguous resource routing
- **Collision Detection**: Detect and warn about duplicate tool or prompt names across servers
- **OpenAI Integration**: Built-in utilities for converting MCP tools to OpenAI function calling format
- **Async Context Manager**: Clean resource management with Python's async context managers

## Installation

```bash
pip install mcp-multi-server
```

Or with Poetry:

```bash
poetry add mcp-multi-server
```

### Optional Dependencies

For OpenAI integration:
```bash
pip install mcp-multi-server[openai]
```

For running examples:
```bash
pip install mcp-multi-server[examples]
```

## Quick Start

### 1. Create a Server Configuration File

Create a `mcp_servers.json` file defining your MCP servers:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python",
      "args": ["-m", "my_servers.filesystem_server"]
    },
    "database": {
      "command": "python",
      "args": ["-m", "my_servers.database_server"]
    }
  }
}
```

### 2. Use the Multi-Server Client

```python
import asyncio
from mcp_multi_server import MultiServerClient

async def main():
    # Using context manager (recommended)
    async with MultiServerClient.from_config("mcp_servers.json") as client:
        # List all available tools from all servers
        tools = client.list_tools()
        print(f"Found {len(tools.tools)} tools")

        # Call a tool (automatically routed to the correct server)
        result = await client.call_tool(
            "read_file",
            {"path": "/path/to/file.txt"}
        )

        # List all resources with namespaced URIs
        resources = client.list_resources()

        # Read a resource (auto-routing via namespace)
        content = await client.read_resource(resources.resources[0].uri)

        # Get a prompt
        prompt = await client.get_prompt("code_review", {"language": "python"})

asyncio.run(main())
```

### 3. Programmatic Configuration

You can also configure servers programmatically without a JSON file:

```python
from mcp_multi_server import MultiServerClient, MCPServersConfig, ServerConfig

config = MCPServersConfig(mcpServers={
    "my_server": ServerConfig(
        command="python",
        args=["-m", "my_package.my_server"]
    )
})

async with MultiServerClient.from_dict(config.model_dump()) as client:
    tools = client.list_tools()
    # ...
```

## OpenAI Integration

The library includes utilities for converting MCP tools to OpenAI function calling format:

```python
from mcp_multi_server import MultiServerClient, mcp_tools_to_openai_format
from openai import OpenAI
import json

async def chat_with_tools():
    async with MultiServerClient.from_config("mcp_servers.json") as mcp_client:
        # Get all tools from all servers
        tools_result = mcp_client.list_tools()

        # Convert to OpenAI format
        openai_tools = mcp_tools_to_openai_format(tools_result.tools)

        # Use with OpenAI
        openai_client = OpenAI()
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "List all files in /home"}],
            tools=openai_tools
        )

        # If OpenAI wants to call a tool, route it through MCP client
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            result = await mcp_client.call_tool(
                tool_call.function.name,
                json.loads(tool_call.function.arguments)
            )
```

## Examples

The repository includes comprehensive examples demonstrating various use cases. See the [examples directory](examples/) for:

- Example MCP server implementations (tools, resources, prompts)
- Example clients showing different usage patterns
- Full chat client with OpenAI integration

## API Reference

### MultiServerClient

Main class for managing multiple MCP servers.

**Class Methods:**
- `from_config(config_path: str)` - Create client from JSON config file
- `from_dict(config_dict: Dict)` - Create client from configuration dictionary

**Instance Methods:**
- `connect_all(stack: AsyncExitStack)` - Connect to all configured servers
- `list_tools()` - Get all tools from all servers
- `list_prompts()` - Get all prompts from all servers
- `list_resources(use_namespace: bool = True)` - Get all resources
- `list_resource_templates(use_namespace: bool = True)` - Get all resource templates
- `call_tool(name, arguments, server_name=None)` - Call a tool
- `read_resource(uri, server_name=None)` - Read a resource
- `get_prompt(name, arguments=None, server_name=None)` - Get a prompt
- `print_capabilities_summary()` - Print discovered capabilities

### Utility Functions

- `mcp_tools_to_openai_format(tools)` - Convert MCP tools to OpenAI function format
- `format_namespace_uri(server_name, uri)` - Create namespaced URI
- `parse_namespace_uri(uri)` - Parse namespaced URI
- `extract_template_variables(template)` - Extract variables from URI template
- `substitute_template_variables(template, variables)` - Substitute template variables

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- **Documentation**: https://multi-server-client.readthedocs.io/
- **Source Code**: https://github.com/apisani1/multi-server-client
- **Issue Tracker**: https://github.com/apisani1/multi-server-client/issues
- **MCP Protocol**: https://modelcontextprotocol.io
