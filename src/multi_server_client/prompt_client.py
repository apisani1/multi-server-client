import asyncio
import traceback
from typing import List

from mcp import (
    ClientSession,
    StdioServerParameters,
)
from mcp.client.stdio import stdio_client
from mcp.types import (
    AudioContent,
    EmbeddedResource,
    ImageContent,
    ListPromptsResult,
    Prompt,
    PromptMessage,
    ResourceLink,
    TextContent,
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
    args=["run", "python3", "-m", "src.multi_server_client.prompt_server"],  # Optional command line arguments
)


def print_prompts(prompts: ListPromptsResult) -> None:
    for i, prompt in enumerate(prompts.prompts):
        print(f"Prompt[{i}] attributes:")
        print(f"- Name: {prompt.name}")
        print(f"- Description: {prompt.description}")
        print(f"- Arguments: {prompt.arguments}")
        print("-" * 20)


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


def print_messages(messages: List[PromptMessage]) -> None:
    """Print a list of messages, showing text content or content type/mime type."""
    for i, message in enumerate(messages):
        print(f"Message {i} ({message.role}):")
        # print(f"Content type: {type(message.content)}")

        if isinstance(message.content, str):
            print(f"  {message.content}")
        elif isinstance(message.content, TextContent):
            print(f"  Content Type: text: {message.content.text}")
        elif isinstance(message.content, ImageContent):
            print(f"  Content Type: image, MIME Type: {message.content.mimeType}")
            display_image_content(message.content)
        elif isinstance(message.content, AudioContent):
            print(f"  Content Type: audio, MIME Type: {message.content.mimeType}")
            display_audio_content(message.content)
        elif isinstance(message.content, EmbeddedResource):
            print("  Content Type: embedded resource")
            # Ask user for output filename
            filename = input("Enter filename to save binary file to: ").strip()
            if filename:
                decode_binary_file(message.content, filename)
            else:
                print("  Skipped saving binary file (no filename provided)")
        elif isinstance(message.content, ResourceLink):
            print("  Content Type: resource link")
            print(f"  URI: {message.content.uri}")
            print(f"  MIME Type: {message.content.mimeType}")
            display_content_from_uri(message.content)
        elif hasattr(message.content, "type"):
            content_type = message.content.type
            mime_type = getattr(message.content, "mimeType", "N/A")
            print(f"  Content Type: {content_type}, MIME Type: {mime_type}")
        else:
            print(f"  Unknown content type: {type(message.content)}")
        print()


async def run() -> None:
    try:
        print("Starting prompt_client...")
        async with stdio_client(server_params) as (read, write):
            print("Client connected, creating session...")
            async with ClientSession(read, write) as session:

                print("Initializing session...")
                await session.initialize()

                prompts = await session.list_prompts()
                print_prompts(prompts)

                print("Getting prompt...")
                index = int(input("Choose a prompt and press Enter to continue..."))
                prompt = prompts.prompts[index]
                arguments = get_prompt_arguments(prompt)
                result = await session.get_prompt(name=prompt.name, arguments=arguments)

                print_messages(result.messages)

    except Exception:
        print("An error occurred:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run())
