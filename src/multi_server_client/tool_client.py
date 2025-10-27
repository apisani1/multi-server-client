import asyncio
import json
import traceback
from typing import Any

from mcp import (
    ClientSession,
    StdioServerParameters,
)
from mcp.client.stdio import stdio_client
from mcp.types import (
    AudioContent,
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    ListToolsResult,
    ResourceLink,
    TextContent,
    Tool,
)


try:
    from .media_handler import (
        decode_binary_file,
        display_audio_content,
        display_content_from_uri,
        display_image_content,
    )
except ImportError:
    from src.multi_server_client.media_handler import (
        decode_binary_file,
        display_audio_content,
        display_content_from_uri,
        display_image_content,
    )


server_params = StdioServerParameters(
    command="poetry",
    args=["run", "python3", "-m", "src.multi_server_client.tool_server"],  # Run as module to fix imports
)


def print_tools(tools: ListToolsResult) -> None:
    for i, tool in enumerate(tools.tools):
        print(f"Tool[{i}] attributes:")
        print(f"- Name: {tool.name}")
        print(f"- Description: {tool.description}")
        print(f"- Input Schema: {tool.inputSchema}")
        print("-" * 20)


def get_tool_arguments(tool: Tool) -> dict[str, Any]:  # pylint: disable=too-many-locals
    """Ask user for tool arguments interactively."""
    arguments: dict[str, Any] = {}

    if not tool.inputSchema:
        return arguments

    print(f"\nEntering arguments for tool '{tool.name}':")
    print(f"Description: {tool.description}")

    properties = tool.inputSchema.get("properties", {})
    required_props = tool.inputSchema.get("required", [])
    definitions = tool.inputSchema.get("$defs", {})

    def get_object_properties(schema_ref: str) -> dict:
        """Get properties from a $ref definition."""
        ref_name = schema_ref.split("/")[-1]  # Extract name from "#/$defs/Person"
        return definitions.get(ref_name, {}).get("properties", {})

    def get_object_required(schema_ref: str) -> list:
        """Get required fields from a $ref definition."""
        ref_name = schema_ref.split("/")[-1]
        return definitions.get(ref_name, {}).get("required", [])

    def convert_value(value: str, value_type: str) -> Any:
        """Convert string input to appropriate type."""
        if value_type == "integer":
            return int(value)
        if value_type == "number":
            return float(value)
        if value_type == "boolean":
            return value.lower() in ("true", "1", "yes", "y")
        if value_type == "array":
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def get_property_input(
        prop_name: str, description: str, prop_type: str, is_required: bool, indent: str = ""
    ) -> Any:
        """Get input for a single property with validation."""
        required_marker = "(required)" if is_required else ""
        prompt = f"{indent}Enter '{prop_name}'{required_marker} ({description}) [{prop_type}]: "

        while True:
            value = input(prompt).strip()

            # Handle required fields
            if is_required and not value:
                print(f"{indent}Error: '{prop_name}' is required. Please provide a value.")
                continue

            # Skip optional empty fields
            if not value:
                return None

            # Type conversion
            try:
                return convert_value(value, prop_type)
            except ValueError:
                print(f"{indent}Error: Invalid {prop_type} value. Please try again.")

    # get the tool argument using the tool's input schema
    for prop, schema in properties.items():
        description = schema.get("description", "")
        prop_type = schema.get("type", "string")
        is_required = prop in required_props

        # Handle $ref (object references)
        if "$ref" in schema:
            print(f"\n--- Entering object '{prop}' ---")
            obj_properties = get_object_properties(schema["$ref"])
            obj_required = get_object_required(schema["$ref"])

            obj_data = {}
            for obj_prop, obj_schema in obj_properties.items():
                obj_description = obj_schema.get("description", "")
                obj_type = obj_schema.get("type", "string")
                obj_is_required = obj_prop in obj_required

                result = get_property_input(obj_prop, obj_description, obj_type, obj_is_required, "  ")
                if result is not None:
                    obj_data[obj_prop] = result

            arguments[prop] = obj_data
        else:
            # Handle simple properties
            result = get_property_input(prop, description, prop_type, is_required)
            if result is not None:
                arguments[prop] = result

    return arguments


def print_tool_result(result: CallToolResult) -> None:
    """Print tool result, showing text content or content type/mime type."""

    if result.isError:
        print("Tool call resulted in error")
        return

    for i, block in enumerate(result.content):
        print(f"Block {i}:")

        if isinstance(block, TextContent):
            print("Content Type: text:")
            print(f"{block.text}")
        elif isinstance(block, ImageContent):
            print(f"Content Type: image, MIME Type: {block.mimeType}")
            display_image_content(block)
        elif isinstance(block, AudioContent):
            print(f"Content Type: audio, MIME Type: {block.mimeType}")
            display_audio_content(block)
        elif isinstance(block, EmbeddedResource):
            print("Content Type: embedded resource")
            # Ask user for output filename
            filename = input("Enter filename to save binary file to: ").strip()
            if filename:
                decode_binary_file(block, filename)
            else:
                print("Skipped saving binary file (no filename provided)")
        elif isinstance(block, ResourceLink):
            print("Content Type: resource link")
            print(f"URI: {block.uri}")
            print(f"MIME Type: {block.mimeType}")
            display_content_from_uri(block)
        elif hasattr(block, "type"):
            content_type = block.type
            mime_type = getattr(block, "mimeType", "N/A")
            print(f"ontent Type: {content_type}, MIME Type: {mime_type}")
        else:
            print(f"Unknown content type: {type(block)}")

        if result.structuredContent:
            print("Structured Content:")
            print(json.dumps(result.structuredContent, indent=2))

        print()


async def run() -> None:
    try:
        print("Starting tool_client...")
        async with stdio_client(server_params) as (read, write):
            print("Client connected, creating session...")
            async with ClientSession(read, write) as session:

                print("Initializing session...")
                await session.initialize()

                print("Listing tools...")
                tools = await session.list_tools()
                print_tools(tools)

                print("Calling tool...")
                index = int(input("Choose a tool and press Enter to continue..."))
                tool = tools.tools[index]
                arguments = get_tool_arguments(tool)
                result = await session.call_tool(name=tool.name, arguments=arguments)

                print_tool_result(result)

    except Exception:
        print("An error occurred:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run())
