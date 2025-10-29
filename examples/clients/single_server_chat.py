import asyncio
import json
import os
import traceback

from dotenv import (
    find_dotenv,
    load_dotenv,
)
from mcp import (
    ClientSession,
    StdioServerParameters,
)
from mcp.client.stdio import stdio_client
from mcp.types import ListToolsResult
from openai import OpenAI


load_dotenv(find_dotenv())
assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not found"

MODEL = "gpt-4o"

server_params = StdioServerParameters(
    command="poetry",
    args=["run", "python3", "-m", "examples.servers.tool_server"],
)


def print_server_params(server_params: StdioServerParameters) -> None:
    print(server_params.command, end=" ")
    for arg in server_params.args:
        print(arg, end=" ")
    print("\n")


def print_tools(tools: ListToolsResult) -> None:
    for i, tool in enumerate(tools.tools):
        print(f"Tool[{i}] attributes:")
        print(f"- Name: {tool.name}")
        print(f"- Description: {tool.description}")
        print(f"- Input Schema: {tool.inputSchema}")
        print("-" * 20)
    print("\n")


async def chat() -> None:
    try:
        print("****Connecting to tool server using:")
        print_server_params(server_params)
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                print("***Listing tools...")
                print_tools(tools_result)

                client = OpenAI()

                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema,
                        },
                    }
                    for tool in tools_result.tools
                ]

                messages = []
                query = input(">")

                while query.lower() not in ("exit", "quit"):
                    # Make OpenAI LLM call to answer the user query
                    messages.append({"role": "user", "content": query})
                    response = client.chat.completions.create(  # type: ignore[call-overload]
                        model=MODEL,
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                    ).choices[0]

                    # Handle any tool calls
                    while response.finish_reason == "tool_calls":
                        messages.append(response.message)
                        for tool_call in response.message.tool_calls:
                            # Execute tool call
                            print(
                                f"****Calling tool: {tool_call.function.name}, with arguments: {tool_call.function.arguments}"
                            )
                            tool_result = await session.call_tool(
                                name=tool_call.function.name,
                                arguments=json.loads(tool_call.function.arguments),
                            )
                            # Add tool response to conversation
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": tool_result.content[0].text,  # type: ignore[union-attr]
                                }
                            )
                            print(f"****Tool result: {tool_result.content[0].text}")  # type: ignore[union-attr]

                        # Get another response from LLM including tool results
                        response = client.chat.completions.create(  # type: ignore[call-overload]
                            model=MODEL,
                            messages=messages,
                            tools=openai_tools,
                            tool_choice="auto",
                        ).choices[0]

                    print(f"\033[93m{response.message.content}\033[0m")
                    messages.append(response.message)
                    query = input(">")

    except Exception:
        print("An error occurred:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(chat())
