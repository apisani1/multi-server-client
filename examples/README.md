# MCP Multi-Server Examples

This directory contains comprehensive examples demonstrating how to use the `mcp-multi-server` library and how to implement your own MCP servers and clients.

## Directory Structure

```
examples/
├── servers/          # Example MCP server implementations
│   ├── tool_server.py      # Server providing tools (member database)
│   ├── resource_server.py  # Server providing resources (inventory management)
│   └── prompt_server.py    # Server providing prompts (templates)
├── clients/          # Example client implementations
│   ├── chat_client.py      # Multi-server chat with OpenAI integration
│   ├── tool_client.py      # Interactive tool exploration
│   ├── resource_client.py  # Interactive resource browsing
│   └── prompt_client.py    # Interactive prompt interface
├── support/          # Supporting modules
│   ├── inventory_db.py     # Inventory database for resource server
│   └── media_handler.py    # Media file handling utilities
├── assets/           # Media assets for examples
│   ├── picture.jpg
│   └── sound.mp3
└── mcp_servers.json  # Configuration for example servers
```

## Prerequisites

Install the library with examples dependencies:

```bash
# From the project root
poetry install --extras examples

# Or with pip
pip install -e ".[examples]"
```

You'll also need to set up an OpenAI API key for the chat client:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Example Servers

### 1. Tool Server ([tool_server.py](servers/tool_server.py))

Demonstrates MCP tools with structured input/output using Pydantic models.

**Features:**
- Member database management (add, get, list, remove members)
- Complex structured data (Person model with addresses)
- Media content (images, audio) in tool results

**Run the server:**
```bash
python -m examples.servers.tool_server
```

**Available Tools:**
- `add_person` - Add a person to the member database
- `get_person` - Get a person by ID
- `list_persons` - List all members
- `add_new_address` - Add an address to a member
- `get_image` - Get image data from a file
- `get_audio` - Get audio data from a file

### 2. Resource Server ([resource_server.py](servers/resource_server.py))

Demonstrates MCP resources for exposing data and using URI templates.

**Features:**
- Inventory management system
- Static resources (overview, stats, items list)
- Dynamic resources with parameters (by ID, by name, by category)
- Resource templates with variable substitution
- Search functionality

**Run the server:**
```bash
python -m examples.servers.resource_server
```

**Available Resources:**
- `inventory://overview` - Inventory overview
- `inventory://items` - All items
- `inventory://stats` - Statistics
- `inventory://low-stock` - Items needing reorder
- `inventory://item/{item_id}` - Item by UUID (template)
- `inventory://item/name/{item_name}` - Item by name (template)
- `inventory://category/{category}` - Items by category (template)
- `inventory://search/{query}` - Search items (template)

### 3. Prompt Server ([prompt_server.py](servers/prompt_server.py))

Demonstrates MCP prompts with parameters and media content.

**Features:**
- Parameterized prompts
- Prompts returning conversation histories
- Embedded images and audio in prompts
- File loading and resource links

**Run the server:**
```bash
python -m examples.servers.prompt_server
```

**Available Prompts:**
- `write_detailed_historical_report` - Generate research report
- `roleplay_scenario` - Set up a roleplay with optional media
- `load_file` - Load a file as an embedded resource
- `send_content_uri` - Send a content URI as a resource link

## Example Clients

### 1. Multi-Server Chat Client ([clients/chat_client.py](clients/chat_client.py))

**PRIMARY EXAMPLE** - Full-featured chat interface integrating multiple MCP servers with OpenAI.

**Features:**
- Connects to all configured servers
- Converts MCP tools to OpenAI function calling format
- Interactive prompt and resource insertion
- Template variable substitution
- Tool call execution with automatic routing

**Run the client:**
```bash
# First, start all three servers in separate terminals
python -m examples.servers.tool_server
python -m examples.servers.resource_server
python -m examples.servers.prompt_server

# Then run the chat client
python -m examples.clients.chat_client
```

**Usage:**
- Normal chat: Type your message
- Insert prompt: `+prompt:write_detailed_historical_report`
- Insert resource: `+resource:inventory://overview`
- Insert template: `+template:inventory://item/{item_id}`
- Type `exit` or `quit` to end

### 2. Tool Client ([clients/tool_client.py](clients/tool_client.py))

Interactive explorer for discovering and calling tools.

**Run:**
```bash
python -m examples.clients.tool_client
```

### 3. Resource Client ([clients/resource_client.py](clients/resource_client.py))

Interactive browser for listing and reading resources.

**Run:**
```bash
python -m examples.clients.resource_client
```

### 4. Prompt Client ([clients/prompt_client.py](clients/prompt_client.py))

Interactive interface for discovering and using prompts.

**Run:**
```bash
python -m examples.clients.prompt_client
```

## Configuration

The [mcp_servers.json](mcp_servers.json) file defines the three example servers:

```json
{
  "mcpServers": {
    "tool_server": {
      "command": "poetry",
      "args": ["run", "python3", "-m", "examples.servers.tool_server"]
    },
    "resource_server": {
      "command": "poetry",
      "args": ["run", "python3", "-m", "examples.servers.resource_server"]
    },
    "prompt_server": {
      "command": "poetry",
      "args": ["run", "python3", "-m", "examples.servers.prompt_server"]
    }
  }
}
```

## Using the Library in Your Code

### Basic Multi-Server Setup

```python
import asyncio
from mcp_multi_server import MultiServerClient

async def main():
    async with MultiServerClient.from_config("examples/mcp_servers.json") as client:
        # Print what's available
        client.print_capabilities_summary()

        # List all tools from all servers
        tools = client.list_tools()
        print(f"Total tools: {len(tools.tools)}")

        # Call a tool (auto-routed to correct server)
        result = await client.call_tool("list_persons", {})
        print(result)

asyncio.run(main())
```

### OpenAI Integration

```python
from mcp_multi_server import MultiServerClient, mcp_tools_to_openai_format
from openai import OpenAI
import json

async def chat():
    async with MultiServerClient.from_config("examples/mcp_servers.json") as mcp_client:
        # Convert MCP tools to OpenAI format
        tools_result = mcp_client.list_tools()
        openai_tools = mcp_tools_to_openai_format(tools_result.tools)

        # Use with OpenAI
        openai_client = OpenAI()
        messages = [{"role": "user", "content": "Add a new person named John Doe"}]

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=openai_tools
        )

        # Handle tool calls
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                result = await mcp_client.call_tool(
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments)
                )
                print(f"Tool result: {result}")
```

## Learning Path

1. **Start with the servers** - Understand how MCP servers expose capabilities
2. **Try the simple clients** - See how to interact with individual capability types
3. **Study the chat client** - Learn complete multi-server integration with OpenAI
4. **Build your own** - Use these examples as templates for your servers and clients

## Common Patterns

### Server Patterns

1. **Tools**: Use `@mcp.tool()` decorator for executable functions
2. **Resources**: Use `@mcp.resource()` for data endpoints
3. **Prompts**: Use `@mcp.prompt()` for prompt templates
4. **Structured Data**: Use Pydantic models for type safety

### Client Patterns

1. **Context Manager**: Always use `async with` for automatic cleanup
2. **Auto-Routing**: Let the client route tools/prompts automatically
3. **Namespaced URIs**: Use server:uri format for resources
4. **Error Handling**: Check `CallToolResult.isError` for tool failures

## Troubleshooting

### Servers won't start
- Check that all dependencies are installed: `poetry install --extras examples`
- Verify Python version >= 3.10
- Check server logs for specific error messages

### Can't connect to servers
- Ensure servers are running before starting client
- Verify paths in mcp_servers.json are correct
- Check that ports aren't already in use

### OpenAI integration issues
- Verify OPENAI_API_KEY environment variable is set
- Check you have sufficient OpenAI API credits
- Ensure you're using a compatible model (gpt-4o, gpt-4-turbo, etc.)

## Next Steps

- Modify the example servers to add your own tools/resources/prompts
- Create your own MCP servers for your specific use cases
- Integrate the multi-server client into your applications
- Explore the main library documentation for advanced features

## Resources

- [MCP Protocol Documentation](https://modelcontextprotocol.io)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/fastmcp)
- [Project Repository](https://github.com/apisani1/mcp-multi-server)
