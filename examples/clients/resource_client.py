import asyncio
import re
import traceback
from urllib.parse import quote

from pydantic import AnyUrl

from mcp import (
    ClientSession,
    StdioServerParameters,
)
from mcp.client.stdio import stdio_client
from mcp.types import (
    BlobResourceContents,
    ReadResourceResult,
    TextResourceContents,
)


server_params = StdioServerParameters(
    command="poetry",
    args=["run", "python3", "-m", "examples.servers.resource_server"],  # Optional command line arguments
)


def print_resource_result(resources: ReadResourceResult) -> None:
    """Print the content of a Resource URI"""
    for i, resource in enumerate(resources.contents):
        print(f"Content {i} ({type(resource)}):")

        if isinstance(resource, TextResourceContents):
            print(f"  {resource.text}")
        elif isinstance(resource, BlobResourceContents):
            print(f"- MIME type: {resource.mimeType}")
            if len(resource.blob) > 50:
                print(f"- Blob data (first 50 bytes): {resource.blob[:50]!r}...")
            else:
                print(f"- Blob data: {resource.blob!r}")
        else:
            print(f"  Unknown content type: {type(resource)}")
        print()


def extract_template_variables(uri_template: str) -> list[str]:
    """Extract variable names from a URI template."""
    pattern = r"\{([^}]+)\}"
    return re.findall(pattern, uri_template)


def get_template_variables_from_user(uri_template: str) -> dict[str, str]:
    """Extract variables from URI template and ask user for values."""
    pattern = r"\{([^}]+)\}"
    variables = re.findall(pattern, uri_template)

    if not variables:
        return {}

    print(f"\nTemplate: {uri_template}")
    print("Please provide values for the following variables:")

    values = {}
    for var in variables:
        value = input(f"Enter value for {var}: ").strip()
        values[var] = value

    return values


def substitute_template_variables(uri_template: str, variables: dict[str, str]) -> str:
    """Substitute variables in URI template with provided values.

    URL-encodes the values to handle spaces and special characters properly.
    """
    result = uri_template
    for var, value in variables.items():
        # URL encode the value to handle spaces and special characters
        encoded_value = quote(value, safe="")
        result = result.replace(f"{{{var}}}", encoded_value)
    return result


async def run() -> None:
    try:
        print("Starting resource_client...")
        async with stdio_client(server_params) as (read, write):
            print("Client connected, creating session...")
            async with ClientSession(read, write) as session:

                print("Initializing session...")
                await session.initialize()

                resources = await session.list_resources()
                print(f"\nFound {len(resources.resources)} resources:")
                for i, resource in enumerate(resources.resources):
                    print(f"Resource[{i}] attributes:")
                    print(f"- Name: {resource.name}")
                    print(f"- Description: {resource.description}")
                    print(f"- URI: {resource.uri}")
                    result = await session.read_resource(uri=AnyUrl(resource.uri))
                    print_resource_result(result)
                    print("-" * 20)

                templates = await session.list_resource_templates()
                print(f"\nFound {len(templates.resourceTemplates)} resource templates:")
                for i, template in enumerate(templates.resourceTemplates):
                    print(f"Template[{i}] attributes:")
                    print(f"- Name: {template.name}")
                    print(f"- Description: {template.description}")
                    print(f"- URI Template: {template.uriTemplate}")
                    variables = extract_template_variables(template.uriTemplate)
                    print(f"Variables in template: {variables}")
                    if variables:
                        var_values = get_template_variables_from_user(template.uriTemplate)
                        uri = substitute_template_variables(template.uriTemplate, var_values)
                    else:
                        uri = template.uriTemplate

                    result = await session.read_resource(uri=AnyUrl(uri))
                    print_resource_result(result)
                    print("-" * 20)

    except Exception:
        print("An error occurred:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run())
