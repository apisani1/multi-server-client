"""Example showing structured input and output with tools."""

import logging
from typing import (
    Dict,
    List,
    Optional,
    TypedDict,
)

from pydantic import (
    BaseModel,
    Field,
)

from mcp.server.fastmcp import FastMCP
from mcp.types import (
    AudioContent,
    CallToolResult,
    ImageContent,
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

# Suppress MCP library INFO logs
logging.getLogger("mcp").setLevel(logging.WARNING)

# Create server
mcp = FastMCP("My Tools")


class Person(BaseModel):
    first_name: str = Field(..., description="The person's first name")
    last_name: str = Field(..., description="The person's last name")
    years_of_experience: int = Field(..., description="Number of years of experience")
    addresses: List[str] = Field(default_factory=list, description="List of previous addresses")


# TypedDict for structured output without using Pydantic
class LocationInfo(TypedDict):
    full_name: str
    addresses: list[str]


class MemberDatabase(BaseModel):
    members: dict[str, Person] = Field(default_factory=dict, description="In-memory database of members")
    next_id: int = Field(default=1, description="Next sequential ID to assign")

    def add_member(self, person: Person) -> str:
        """Add a person to the database with auto-generated sequential ID."""
        member_id = str(self.next_id)
        self.members[member_id] = person
        self.next_id += 1
        return member_id

    def add_member_with_id(self, member_id: str, person: Person) -> str:
        """Add a person to the database with specific ID (legacy method)."""
        self.members[member_id] = person
        return f"Added member {member_id} to database"

    def get_member(self, member_id: str) -> Person | None:
        """Retrieve a person from the database."""
        return self.members.get(member_id)  # pylint: disable=no-member

    def get_member_id(self, first_name: str, last_name: str) -> Optional[str]:
        """Get member ID by first and last name."""
        for member_id, person in self.members.items():  # pylint: disable=no-member
            if person.first_name == first_name and person.last_name == last_name:
                return member_id
        return None

    def list_members(self) -> list[str]:
        """List all member IDs in the database."""
        return list(self.members.keys())  # pylint: disable=no-member

    def remove_member(self, member_id: str) -> str:
        """Remove a person from the database."""
        if member_id in self.members:
            del self.members[member_id]
            return f"Removed member {member_id} from database"
        return f"Member {member_id} not found"


member_db = MemberDatabase()

# Populate with 5 test records
test_people = [
    Person(
        first_name="Alice",
        last_name="Johnson",
        years_of_experience=5,
        addresses=["123 Main St, Springfield", "456 Oak Ave, Portland"],
    ),
    Person(first_name="Bob", last_name="Smith", years_of_experience=10, addresses=["789 Pine Rd, Seattle"]),
    Person(
        first_name="Carol",
        last_name="Davis",
        years_of_experience=3,
        addresses=["321 Elm St, Denver", "654 Maple Dr, Boulder", "987 Cedar Ln, Fort Collins"],
    ),
    Person(first_name="David", last_name="Wilson", years_of_experience=8, addresses=["147 Birch Way, Austin"]),
    Person(
        first_name="Emma",
        last_name="Brown",
        years_of_experience=12,
        addresses=["258 Willow Ct, Miami", "369 Spruce St, Tampa"],
    ),
]

for test_person in test_people:
    member_db.add_member(test_person)


@mcp.tool(name="add_person")
def add_person_to_member_database(person: Person) -> Dict[str, Person]:
    """Logs personal details to the member database."""
    member_id = member_db.add_member(person)
    return {member_id: person}


@mcp.tool(name="list_persons")
def list_member_database_items() -> Dict[str, Dict[str, str]]:
    """List all members in the database."""
    return {k: {"first_name": v.first_name, "last_name": v.last_name} for k, v in member_db.members.items()}


@mcp.tool(name="get_person")
def get_person_from_member_database(member_id: str) -> Optional[Person]:
    """Get a person from the member database by ID."""
    return member_db.get_member(member_id)


@mcp.tool(name="add_new_address")
def add_address_info(member_first_name: str, member_last_name: str, new_address: str) -> LocationInfo:
    """Add new addresss to a database member."""
    member_id = member_db.get_member_id(member_first_name, member_last_name)
    if not member_id:
        return LocationInfo(full_name="Person not found", addresses=[])
    person = member_db.get_member(member_id)
    if not person:
        return LocationInfo(full_name="Person not found", addresses=[])
    person.addresses.append(new_address)
    return LocationInfo(full_name=f"{person.first_name} {person.last_name}", addresses=person.addresses)


# Tools returning other types from media_handler for demonstration


@mcp.tool(name="get_image")
def get_image_tool(image_path: str) -> CallToolResult:
    """Get image data and MIME type from a file."""
    image_data, mime_type = get_image(image_path)
    return CallToolResult(isError=False, content=[ImageContent(type="image", data=image_data, mimeType=mime_type)])


@mcp.tool(name="get_audio")
def get_audio_tool(audio_path: str) -> CallToolResult:
    """Get audio data and MIME type from a file."""
    audio_data, mime_type = get_audio(audio_path)
    return CallToolResult(isError=False, content=[AudioContent(type="audio", data=audio_data, mimeType=mime_type)])


if __name__ == "__main__":
    print("Starting MCP Tool Server...")
    mcp.run()
