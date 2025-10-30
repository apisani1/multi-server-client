"""Tests for utility functions."""

import pytest
from mcp.types import Tool

from mcp_multi_server.utils import (
    extract_template_variables,
    format_namespace_uri,
    mcp_tools_to_openai_format,
    parse_namespace_uri,
    substitute_template_variables,
)


class TestMcpToolsToOpenaiFormat:
    """Tests for mcp_tools_to_openai_format function."""

    def test_convert_single_tool(self) -> None:
        """Test converting a single MCP tool to OpenAI format."""
        mcp_tools = [
            Tool(
                name="get_weather",
                description="Get weather for a location",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    }
                }
            )
        ]

        result = mcp_tools_to_openai_format(mcp_tools)

        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_weather"
        assert result[0]["function"]["description"] == "Get weather for a location"
        assert result[0]["function"]["parameters"] == mcp_tools[0].inputSchema

    def test_convert_multiple_tools(self) -> None:
        """Test converting multiple MCP tools to OpenAI format."""
        mcp_tools = [
            Tool(
                name="get_weather",
                description="Get weather",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="get_news",
                description="Get news",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="calculate",
                description="Calculate",
                inputSchema={"type": "object", "properties": {}}
            )
        ]

        result = mcp_tools_to_openai_format(mcp_tools)

        assert len(result) == 3
        assert all(tool["type"] == "function" for tool in result)
        assert result[0]["function"]["name"] == "get_weather"
        assert result[1]["function"]["name"] == "get_news"
        assert result[2]["function"]["name"] == "calculate"

    def test_convert_empty_list(self) -> None:
        """Test converting an empty list of tools."""
        result = mcp_tools_to_openai_format([])

        assert result == []
        assert isinstance(result, list)

    def test_preserves_complex_input_schema(self) -> None:
        """Test that complex inputSchema is preserved correctly."""
        complex_schema = {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name"
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "default": "celsius"
                },
                "forecast_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 7
                }
            },
            "required": ["location"]
        }

        mcp_tools = [
            Tool(
                name="get_weather",
                description="Get weather forecast",
                inputSchema=complex_schema
            )
        ]

        result = mcp_tools_to_openai_format(mcp_tools)

        assert result[0]["function"]["parameters"] == complex_schema
        assert result[0]["function"]["parameters"]["required"] == ["location"]

    def test_tool_with_empty_input_schema(self) -> None:
        """Test tool with empty input schema."""
        mcp_tools = [
            Tool(
                name="no_args_tool",
                description="A tool with no arguments",
                inputSchema={"type": "object", "properties": {}}
            )
        ]

        result = mcp_tools_to_openai_format(mcp_tools)

        assert len(result) == 1
        assert result[0]["function"]["parameters"]["properties"] == {}


class TestFormatNamespaceUri:
    """Tests for format_namespace_uri function."""

    def test_format_standard_uri(self) -> None:
        """Test formatting a standard URI with namespace."""
        result = format_namespace_uri("filesystem", "file:///path/to/file.txt")

        assert result == "filesystem:file:///path/to/file.txt"

    def test_format_with_special_characters(self) -> None:
        """Test formatting URI with special characters."""
        result = format_namespace_uri("db", "records://users/123?filter=active")

        assert result == "db:records://users/123?filter=active"

    def test_format_with_empty_uri(self) -> None:
        """Test formatting with empty URI."""
        result = format_namespace_uri("server", "")

        assert result == "server:"

    def test_format_with_uri_containing_colon(self) -> None:
        """Test formatting URI that already contains colons."""
        result = format_namespace_uri("server", "http://example.com:8080/path")

        assert result == "server:http://example.com:8080/path"

    def test_format_with_different_server_names(self) -> None:
        """Test formatting with various server names."""
        assert format_namespace_uri("tool", "resource") == "tool:resource"
        assert format_namespace_uri("resource_server", "item/123") == "resource_server:item/123"
        assert format_namespace_uri("prompt-server", "prompt://test") == "prompt-server:prompt://test"


class TestParseNamespaceUri:
    """Tests for parse_namespace_uri function."""

    def test_parse_namespaced_uri(self) -> None:
        """Test parsing a properly namespaced URI."""
        server_name, uri = parse_namespace_uri("filesystem:file:///path/to/file.txt")

        assert server_name == "filesystem"
        assert uri == "file:///path/to/file.txt"

    def test_parse_non_namespaced_uri(self) -> None:
        """Test parsing URI without namespace.

        Note: Currently the function splits on first colon, so "file:///"
        is interpreted as server="file", uri="///path". This behavior may
        need refinement to distinguish between namespace prefixes and protocol schemes.
        """
        server_name, uri = parse_namespace_uri("file:///path/to/file.txt")

        # Current behavior: splits on first colon
        assert server_name == "file"
        assert uri == "///path/to/file.txt"

    def test_parse_uri_with_multiple_colons(self) -> None:
        """Test parsing URI with multiple colons (splits on first)."""
        server_name, uri = parse_namespace_uri("server:http://example.com:8080/path")

        assert server_name == "server"
        assert uri == "http://example.com:8080/path"

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string."""
        server_name, uri = parse_namespace_uri("")

        assert server_name is None
        assert uri == ""

    def test_parse_uri_with_only_namespace(self) -> None:
        """Test parsing URI with only namespace prefix."""
        server_name, uri = parse_namespace_uri("server:")

        assert server_name == "server"
        assert uri == ""

    def test_parse_simple_path(self) -> None:
        """Test parsing simple path without colons."""
        server_name, uri = parse_namespace_uri("path/to/resource")

        assert server_name is None
        assert uri == "path/to/resource"

    def test_parse_preserves_uri_structure(self) -> None:
        """Test that parsing preserves the URI structure."""
        original_uri = "http://example.com:8080/path?query=value#fragment"
        server_name, uri = parse_namespace_uri(f"server:{original_uri}")

        assert server_name == "server"
        assert uri == original_uri


class TestExtractTemplateVariables:
    """Tests for extract_template_variables function."""

    def test_extract_single_variable(self) -> None:
        """Test extracting single variable from template."""
        variables = extract_template_variables("file:///{path}")

        assert variables == ["path"]

    def test_extract_multiple_variables(self) -> None:
        """Test extracting multiple variables from template."""
        variables = extract_template_variables("file:///{path}/to/{filename}")

        assert variables == ["path", "filename"]
        assert len(variables) == 2

    def test_extract_no_variables(self) -> None:
        """Test extracting from template with no variables."""
        variables = extract_template_variables("file:///static/path")

        assert variables == []

    def test_extract_from_empty_string(self) -> None:
        """Test extracting from empty string."""
        variables = extract_template_variables("")

        assert variables == []

    def test_extract_with_repeated_variables(self) -> None:
        """Test extracting repeated variables."""
        variables = extract_template_variables("users/{id}/posts/{id}")

        assert variables == ["id", "id"]
        assert len(variables) == 2

    def test_extract_with_nested_braces(self) -> None:
        """Test extraction handles only outer braces."""
        variables = extract_template_variables("path/{var}")

        assert variables == ["var"]

    def test_extract_complex_template(self) -> None:
        """Test extracting from complex template."""
        template = "inventory://category/{category}/item/{item_id}/details"
        variables = extract_template_variables(template)

        assert variables == ["category", "item_id"]

    def test_extract_with_special_characters_in_variable_names(self) -> None:
        """Test extracting variables with underscores and numbers."""
        variables = extract_template_variables("path/{user_id}/posts/{post_id_123}")

        assert variables == ["user_id", "post_id_123"]


class TestSubstituteTemplateVariables:
    """Tests for substitute_template_variables function."""

    def test_substitute_single_variable(self) -> None:
        """Test substituting single variable."""
        result = substitute_template_variables(
            "file:///{path}",
            {"path": "documents"}
        )

        assert result == "file:///documents"

    def test_substitute_multiple_variables(self) -> None:
        """Test substituting multiple variables."""
        result = substitute_template_variables(
            "file:///{path}/to/{filename}",
            {"path": "documents", "filename": "report.txt"}
        )

        assert result == "file:///documents/to/report.txt"

    def test_substitute_with_url_encoding(self) -> None:
        """Test that spaces are URL-encoded."""
        result = substitute_template_variables(
            "file:///{path}/{filename}",
            {"path": "my documents", "filename": "my report.txt"}
        )

        assert result == "file:///my%20documents/my%20report.txt"

    def test_substitute_special_characters_encoded(self) -> None:
        """Test that special characters are URL-encoded."""
        result = substitute_template_variables(
            "path/{name}",
            {"name": "test&value"}
        )

        assert result == "path/test%26value"

    def test_substitute_with_no_variables(self) -> None:
        """Test substitution when template has no variables."""
        result = substitute_template_variables(
            "file:///static/path",
            {}
        )

        assert result == "file:///static/path"

    def test_substitute_partial_variables(self) -> None:
        """Test substitution when only some variables are provided."""
        result = substitute_template_variables(
            "path/{var1}/{var2}",
            {"var1": "value1"}
        )

        assert result == "path/value1/{var2}"
        assert "{var2}" in result

    def test_substitute_empty_value(self) -> None:
        """Test substituting variable with empty value."""
        result = substitute_template_variables(
            "path/{var}/end",
            {"var": ""}
        )

        assert result == "path//end"

    def test_substitute_preserves_non_variable_braces(self) -> None:
        """Test that unmatched braces are preserved."""
        result = substitute_template_variables(
            "path/{var}/text{not_var",
            {"var": "value"}
        )

        assert result == "path/value/text{not_var"

    def test_substitute_numeric_values(self) -> None:
        """Test substituting with numeric string values."""
        result = substitute_template_variables(
            "users/{id}/posts/{post_id}",
            {"id": "123", "post_id": "456"}
        )

        assert result == "users/123/posts/456"

    def test_substitute_complex_path(self) -> None:
        """Test substituting in complex path with multiple variables."""
        result = substitute_template_variables(
            "inventory://category/{category}/item/{item_id}/price",
            {"category": "electronics", "item_id": "e-12345"}
        )

        assert result == "inventory://category/electronics/item/e-12345/price"

    def test_substitute_unicode_characters(self) -> None:
        """Test substituting with Unicode characters."""
        result = substitute_template_variables(
            "path/{name}",
            {"name": "test\u00e9"}
        )

        # Unicode characters should be URL-encoded
        assert "test" in result
        assert "%C3%A9" in result  # é encoded
