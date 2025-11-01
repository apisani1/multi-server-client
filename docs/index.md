# MCP Multi-Server Documentation

A Python library for managing connections to multiple [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers with unified capability discovery, intelligent routing, and seamless OpenAI integration.

## Overview

MCP Multi-Server simplifies the complexity of working with multiple MCP servers by providing:

- **Unified Management**: Single interface to connect and manage multiple MCP servers simultaneously
- **Automatic Discovery**: Discover and aggregate tools, resources, prompts, and templates from all connected servers
- **Intelligent Routing**: Automatically route tool calls, resource reads, and prompt retrievals to the correct server
- **Collision Detection**: Detect and warn about duplicate tool or prompt names across servers
- **Namespace Support**: Use namespaced URIs (server:uri) for unambiguous resource routing
- **OpenAI Integration**: Built-in utilities for converting MCP tools to OpenAI function calling format
- **Type Safety**: Full type hints and Pydantic validation for configuration and data models

## Key Features

### Multi-Server Orchestration
Connect to multiple MCP servers and manage them through a single client interface with automatic lifecycle management using Python's async context managers.

### Capability Aggregation
Automatically discover and aggregate all capabilities (tools, resources, prompts, resource templates) from all connected servers into a unified view.

### Smart Routing
- **Tools & Prompts**: Auto-route by name - no need to specify which server
- **Resources**: Support for namespaced URIs (`server:resource://path`) for explicit routing
- **Explicit Override**: Optionally specify target server for any operation

### Developer Experience
- Simple programmatic or file-based configuration
- Comprehensive error handling with custom exceptions
- Full async/await support
- Rich logging for debugging
- 83% test coverage

## Quick Start

### Installation

```bash
pip install mcp-multi-server
```

Or with Poetry:

```bash
poetry add mcp-multi-server
```

### Basic Usage

```python
import asyncio
from mcp_multi_server import MultiServerClient

async def main():
    # Connect to multiple servers from config file
    async with MultiServerClient.from_config("mcp_servers.json") as client:
        # List all tools from all servers
        tools = client.list_tools()
        print(f"Found {len(tools.tools)} tools across all servers")

        # Call a tool (automatically routed to correct server)
        result = await client.call_tool(
            "read_file",
            {"path": "/path/to/file.txt"}
        )

        # List resources with server namespaces
        resources = client.list_resources()

        # Read a resource (auto-routing via namespace)
        content = await client.read_resource(
            "filesystem:file:///path/to/file.txt"
        )

        # Get a prompt with parameters
        prompt = await client.get_prompt(
            "code_review",
            {"language": "python"}
        )

asyncio.run(main())
```

### Configuration

Create a `mcp_servers.json` file:

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

## Documentation Contents

```{toctree}
:hidden:
:maxdepth: 2
:caption: Getting Started

Home <self>
```

<!--
Guides coming soon - uncomment as they are created:

```{toctree}
:hidden:
:maxdepth: 2
:caption: Getting Started

guides/installation
guides/quickstart
guides/configuration
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: User Guides

guides/multi-server-usage
guides/openai-integration
guides/migration-single-to-multi
guides/advanced-features
guides/architecture
```
-->

```{toctree}
:hidden:
:maxdepth: 3
:caption: API Reference

api/modules
```

```{toctree}
:hidden:
:maxdepth: 1
:caption: Links

GitHub Repository <https://github.com/apisani1/mcp-multi-server>
PyPI Package <https://pypi.org/project/mcp-multi-server/>
Issue Tracker <https://github.com/apisani1/mcp-multi-server/issues>
Examples <https://github.com/apisani1/mcp-multi-server/tree/main/examples>
```

## Use Cases

- **AI Agents**: Build agents that can interact with multiple data sources and tools
- **Multi-Domain Applications**: Access capabilities from different domains (filesystem, database, APIs)
- **OpenAI Function Calling**: Convert MCP tools to OpenAI format for seamless integration
- **Microservices**: Aggregate capabilities from multiple microservices
- **Development Tools**: Create unified interfaces for development tooling

## Next Steps

- [API Reference](api/modules.rst) - Detailed API documentation
- [Examples](https://github.com/apisani1/mcp-multi-server/tree/main/examples) - Working examples and sample servers

<!--
Coming soon - uncomment as guides are created:
- [Installation Guide](guides/installation.md) - Get set up with MCP Multi-Server
- [Quick Start](guides/quickstart.md) - Your first multi-server application
- [Configuration Reference](guides/configuration.md) - Complete configuration documentation
-->

## Project Status

- **Version**: 0.1.0
- **Status**: Alpha/Beta - Production ready
- **Python**: 3.10+
- **Test Coverage**: 83%
- **License**: MIT

## Support

- **Issues**: [GitHub Issues](https://github.com/apisani1/mcp-multi-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/apisani1/mcp-multi-server/discussions)
- **Documentation**: This site
- **Examples**: [examples/](https://github.com/apisani1/mcp-multi-server/tree/main/examples)
