import asyncio
import json
import os
import re
import traceback
from contextlib import AsyncExitStack
from typing import (
    Any,
    Dict,
    List,
    Union,
)
from urllib.parse import quote

from dotenv import (
    find_dotenv,
    load_dotenv,
)
from mcp.types import (
    Prompt,
    Resource,
    ResourceTemplate,
    Tool,
)
from openai import OpenAI
from src.multi_server_client.multi_server_client import MultiServerClient


load_dotenv(find_dotenv())
assert os.getenv("OPENAI_API_KEY"), "Error: OPENAI_API_KEY not found in environment"

MODEL = "gpt-4o"


async def search_and_instantiate_prompt(client: MultiServerClient, prompts: List[Prompt], name: str) -> str:
    """Retrieve a prompt by name from the list of prompts.

    Args:
        client: MultiServerClient instance.
        prompts: List of prompt dictionaries.
        name: Name of the prompt to retrieve.

    Returns:
        The prompt text.

    """
    if prompts:
        for prompt in prompts:
            if prompt.name == name:
                prompt_result = await client.get_prompt(name, arguments=get_prompt_arguments(prompt))
                # Assuming single text message prompt
                return prompt_result.messages[0].content.text if prompt_result.messages else ""  # type: ignore[union-attr]
    return ""


def get_prompt_arguments(prompt: Prompt) -> dict[str, str]:
    """Ask user for prompt arguments interactively."""
    arguments: dict[str, str] = {}

    if not prompt.arguments:
        return arguments

    print(f"\nEntering arguments for prompt '{prompt.name}':")
    print(f"Description: {prompt.description}")
    print("(Leave empty for optional arguments)\n")

    for arg in prompt.arguments:
        required_text = "(required)" if arg.required else "(optional)"
        user_input = input(f"Enter {arg.name} {required_text}: ").strip()

        if user_input or arg.required:
            arguments[arg.name] = user_input

    return arguments


async def search_and_instantiate_resource(
    client: MultiServerClient, resources: List[Union[Resource, ResourceTemplate]], name: str, is_template: bool = False
) -> str:
    """Retrieve a resource by name from the list of resources.

    Args:
        client: MultiServerClient instance.
        resources: List of resource dictionaries.
        name: Name of the resource to retrieve.

    Returns:
        The resource content.

    """
    if resources:
        for resource in resources:
            if resource.name == name:
                if not is_template:
                    uri = resource.uri  # type: ignore[union-attr]
                else:
                    uri_template = resource.uriTemplate  # type: ignore[union-attr]
                    variables = extract_template_variables(uri_template)
                    print(f"Variables in template: {variables}")
                    if variables:
                        var_values = get_template_variables_from_user(uri_template)
                        uri = substitute_template_variables(uri_template, var_values)
                    else:
                        uri = uri_template
                resource_result = await client.read_resource(uri=uri)
                # Assuming single text message resource
                return resource_result.contents[0].text if resource_result.contents else ""  # type: ignore[union-attr]
    return ""


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


async def chat(config_path: str = "mcp_servers.json") -> None:
    """Run the multi-server chat interface.

    Args:
        config_path: Path to the server configuration file.
    """

    try:
        async with AsyncExitStack() as stack:
            # Initialize multi-server client
            client = MultiServerClient(config_path)
            await client.connect_all(stack)

            # Print capabilities summary
            client.print_capabilities_summary()

            # Fetch all prompts and resources from all servers
            all_prompts = client.list_prompts().prompts
            all_resources = client.list_resources().resources
            all_resource_templates = client.list_resource_templates().resourceTemplates

            # Get all tools for OpenAI using the new list_tools() method
            tools_result = client.list_tools()
            all_tools: List[Tool] = tools_result.tools or []

            # Convert MCP tools to OpenAI format
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                }
                for tool in all_tools
            ]

            # Initialize OpenAI client
            openai_client = OpenAI()

            # Chat loop
            messages: List[Dict[str, Any]] = []
            print("Multi-Server MCP Chat Client")
            print("Type 'exit' or 'quit' to end the conversation\n")

            query = input("> ")

            while query.lower() not in ("exit", "quit"):

                # Add user message, prompt or resource
                if query.startswith("+prompt:"):
                    prompt = await search_and_instantiate_prompt(client, all_prompts, query[len("+prompt:") :].strip())
                    if not prompt:
                        print(f"Prompt '{query[len('+prompt:') :].strip()}' not found.")
                    else:

                        print(f"****Retrieved prompt content:\n{prompt}\n")

                        messages.append({"role": "user", "content": prompt})
                    query = input("> ")
                    continue

                if query.startswith("+resource:"):
                    resource_name = query[len("+resource:") :].strip()
                    # List variance: List[Resource] not compatible with List[Union[Resource, ResourceTemplate]]
                    resource = await search_and_instantiate_resource(
                        client, all_resources, resource_name  # type: ignore[arg-type]
                    )
                    if not resource:
                        print(f"Resource '{resource_name}' not found.")
                    else:

                        print(f"****Retrieved resource content:\n{resource}\n")

                        messages.append({"role": "user", "content": resource})
                    query = input("> ")
                    continue

                if query.startswith("+template:"):
                    template_name = query[len("+template:") :].strip()
                    # List variance: List[ResourceTemplate] not compatible with List[Union[...]]
                    resource = await search_and_instantiate_resource(
                        client, all_resource_templates, template_name, is_template=True  # type: ignore[arg-type]
                    )
                    if not resource:
                        print(f"Resource Template '{template_name}' not found.")
                    else:

                        print(f"****Instantiated template content:\n{resource}\n")

                        messages.append({"role": "user", "content": resource})
                    query = input("> ")
                    continue

                messages.append({"role": "user", "content": query})

                # Make OpenAI LLM call to answer the user query
                response = openai_client.chat.completions.create(  # type: ignore[call-overload]
                    model=MODEL,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,
                    tool_choice="auto" if openai_tools else None,
                ).choices[0]

                # Handle tool calls
                while response.finish_reason == "tool_calls":
                    messages.append(response.message)

                    for tool_call in response.message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)

                        print(f"\n[Tool Call] {tool_name}")
                        print(f"[Arguments] {json.dumps(tool_args, indent=2)}")

                        # Execute tool via appropriate server
                        try:
                            tool_result = await client.call_tool(tool_name, tool_args)

                            # Todo: Handle different content types more robustly
                            # Extract text content
                            result_text = (
                                tool_result.content[0].text
                                if hasattr(tool_result.content[0], "text")
                                else str(tool_result.content[0])
                            )

                            print(f"[Result] {result_text}\n")

                            # Add tool response to conversation
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": result_text,
                                }
                            )

                        except Exception as e:
                            error_msg = f"Error executing tool {tool_name}: {str(e)}"
                            print(f"[Error] {error_msg}\n")
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": error_msg,
                                }
                            )

                    # Get next response from LLM with tool results
                    response = openai_client.chat.completions.create(  # type: ignore[call-overload]
                        model=MODEL,
                        messages=messages,
                        tools=openai_tools if openai_tools else None,
                        tool_choice="auto" if openai_tools else None,
                    ).choices[0]

                # Print assistant response
                print(f"\n\033[93m{response.message.content}\033[0m\n")
                messages.append(response.message)

                # Get next user input
                query = input("> ")

    except FileNotFoundError as e:
        print(f"Configuration error: {e}")
    except Exception:
        print("An error occurred:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(chat())
