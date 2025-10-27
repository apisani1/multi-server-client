import base64
import mimetypes
from typing import (
    List,
    Optional,
)

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import (
    AssistantMessage,
    Message,
    UserMessage,
)
from mcp.types import (
    AudioContent,
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    ResourceLink,
    TextContent,
)


try:
    from .media_handler import (
        get_audio,
        get_image,
    )
except ImportError:
    from src.multi_server_client.media_handler import (
        get_audio,
        get_image,
    )


mcp = FastMCP("My Prompts")


@mcp.prompt()
def write_detailed_historical_report(topic: str, number_of_paragraphs: int) -> str:
    """
    Writes a detailed historical report
    Args:
        topic: the topic to do research on
        number_of_paragraphs: the number of paragraphs that the main body should be
    """

    prompt = """
    Create a concise research report on the history of {topic}.
    The report should contain 3 sections: INTRODUCTION, MAIN, and CONCLUSION.
    The MAIN section should be {number_of_paragraphs} paragraphs long.
    Include a timeline of key events.
    The conclusion should be in bullet points format.
    """

    prompt = prompt.format(topic=topic, number_of_paragraphs=number_of_paragraphs)

    return prompt


@mcp.prompt()
def roleplay_scenario(
    character: str,
    situation: str,
    additional_message: Optional[str] = None,
    image_path: Optional[str] = None,
    audio_path: Optional[str] = None,
) -> List[Message]:
    """Sets up a roleplaying scenario with initial messages."""

    messages = [
        UserMessage(content=f"Let's roleplay. You are {character}. The situation is: {situation}"),
        AssistantMessage(content="Okay, I understand. I am ready. What happens next?"),
    ]

    if additional_message:
        messages.append(UserMessage(content=TextContent(type="text", text=additional_message)))

    if image_path:
        image_data, image_mime_type = get_image(image_path)
        messages.append(UserMessage(content=ImageContent(type="image", data=image_data, mimeType=image_mime_type)))

    if audio_path:
        audio_data, audio_mime_type = get_audio(audio_path)
        messages.append(UserMessage(content=AudioContent(type="audio", data=audio_data, mimeType=audio_mime_type)))

    return messages


@mcp.prompt()
def load_file(file_path: str) -> List[Message]:
    """Loads a file and returns its contents as an embedded resource."""
    with open(file_path, "rb") as file:
        file_data = file.read()
    return [
        UserMessage(
            content=EmbeddedResource(
                type="resource",
                resource=BlobResourceContents(
                    uri=f"file://{file_path}",  # type: ignore[arg-type]
                    blob=base64.b64encode(file_data).decode("utf-8"),
                ),
            )
        )
    ]


@mcp.prompt()
def send_content_uri(content_uri: str) -> List[Message]:
    """Sends a content URI as an resource link."""
    return [
        UserMessage(
            content=ResourceLink(
                type="resource_link",
                name=content_uri.split("/")[-1],
                uri=content_uri,  # type: ignore[arg-type]
                mimeType=mimetypes.guess_type(content_uri)[0] or "application/octet-stream",
            )
        )
    ]


if __name__ == "__main__":
    print("Starting MCP PromptServer...")
    mcp.run()
