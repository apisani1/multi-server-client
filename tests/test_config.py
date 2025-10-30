"""Tests for configuration models."""

import pytest
from pydantic import ValidationError

from mcp_multi_server.config import MCPServersConfig, ServerConfig


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_create_valid_config(self) -> None:
        """Test creating a valid server configuration."""
        config = ServerConfig(
            command="python",
            args=["-m", "my_server"]
        )

        assert config.command == "python"
        assert config.args == ["-m", "my_server"]

    def test_create_with_multiple_args(self) -> None:
        """Test creating config with multiple arguments."""
        config = ServerConfig(
            command="poetry",
            args=["run", "python", "-m", "my_package.server"]
        )

        assert config.command == "poetry"
        assert len(config.args) == 4
        assert config.args[0] == "run"

    def test_create_with_empty_args(self) -> None:
        """Test creating config with no arguments."""
        config = ServerConfig(
            command="/usr/bin/my-server",
            args=[]
        )

        assert config.command == "/usr/bin/my-server"
        assert config.args == []

    def test_missing_command_raises_validation_error(self) -> None:
        """Test that missing command field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(args=["-m", "server"])  # type: ignore

        assert "command" in str(exc_info.value)

    def test_missing_args_raises_validation_error(self) -> None:
        """Test that missing args field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(command="python")  # type: ignore

        assert "args" in str(exc_info.value)

    def test_invalid_command_type_raises_validation_error(self) -> None:
        """Test that invalid command type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(command=123, args=[])  # type: ignore

        assert "command" in str(exc_info.value)

    def test_invalid_args_type_raises_validation_error(self) -> None:
        """Test that invalid args type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(command="python", args="not-a-list")  # type: ignore

        assert "args" in str(exc_info.value)

    def test_serialization_to_dict(self) -> None:
        """Test serializing config to dictionary."""
        config = ServerConfig(
            command="python",
            args=["-m", "server"]
        )

        config_dict = config.model_dump()
        assert config_dict == {
            "command": "python",
            "args": ["-m", "server"]
        }

    def test_deserialization_from_dict(self) -> None:
        """Test deserializing config from dictionary."""
        config_dict = {
            "command": "node",
            "args": ["server.js", "--port", "3000"]
        }

        config = ServerConfig.model_validate(config_dict)
        assert config.command == "node"
        assert config.args == ["server.js", "--port", "3000"]


class TestMCPServersConfig:
    """Tests for MCPServersConfig model."""

    def test_create_valid_config_with_single_server(self) -> None:
        """Test creating config with a single server."""
        config = MCPServersConfig(mcpServers={
            "tool_server": ServerConfig(
                command="python",
                args=["-m", "servers.tool_server"]
            )
        })

        assert "tool_server" in config.mcpServers
        assert config.mcpServers["tool_server"].command == "python"

    def test_create_valid_config_with_multiple_servers(self) -> None:
        """Test creating config with multiple servers."""
        config = MCPServersConfig(mcpServers={
            "tool_server": ServerConfig(
                command="python",
                args=["-m", "servers.tool_server"]
            ),
            "resource_server": ServerConfig(
                command="python",
                args=["-m", "servers.resource_server"]
            ),
            "prompt_server": ServerConfig(
                command="node",
                args=["prompt-server.js"]
            )
        })

        assert len(config.mcpServers) == 3
        assert "tool_server" in config.mcpServers
        assert "resource_server" in config.mcpServers
        assert "prompt_server" in config.mcpServers

    def test_create_with_empty_servers_dict(self) -> None:
        """Test creating config with empty servers dictionary."""
        config = MCPServersConfig(mcpServers={})

        assert config.mcpServers == {}
        assert len(config.mcpServers) == 0

    def test_missing_mcpServers_raises_validation_error(self) -> None:
        """Test that missing mcpServers field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServersConfig()  # type: ignore

        assert "mcpServers" in str(exc_info.value)

    def test_invalid_mcpServers_type_raises_validation_error(self) -> None:
        """Test that invalid mcpServers type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServersConfig(mcpServers="not-a-dict")  # type: ignore

        assert "mcpServers" in str(exc_info.value)

    def test_invalid_server_config_raises_validation_error(self) -> None:
        """Test that invalid server config raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServersConfig(mcpServers={
                "tool_server": {"command": "python"}  # Missing 'args' field
            })

        assert "args" in str(exc_info.value)

    def test_serialization_to_dict(self) -> None:
        """Test serializing config to dictionary."""
        config = MCPServersConfig(mcpServers={
            "tool_server": ServerConfig(
                command="python",
                args=["-m", "server"]
            )
        })

        config_dict = config.model_dump()
        assert "mcpServers" in config_dict
        assert "tool_server" in config_dict["mcpServers"]
        assert config_dict["mcpServers"]["tool_server"]["command"] == "python"

    def test_deserialization_from_dict(self) -> None:
        """Test deserializing config from dictionary."""
        config_dict = {
            "mcpServers": {
                "tool_server": {
                    "command": "python",
                    "args": ["-m", "server"]
                },
                "resource_server": {
                    "command": "node",
                    "args": ["server.js"]
                }
            }
        }

        config = MCPServersConfig.model_validate(config_dict)
        assert len(config.mcpServers) == 2
        assert config.mcpServers["tool_server"].command == "python"
        assert config.mcpServers["resource_server"].command == "node"

    def test_nested_validation_error_provides_clear_message(self) -> None:
        """Test that nested validation errors are clear."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServersConfig(mcpServers={
                "server1": ServerConfig(command="python", args=[]),
                "server2": {"command": 123, "args": []},  # Invalid command type
            })

        error_str = str(exc_info.value)
        assert "server2" in error_str
        assert "command" in error_str

    def test_accessing_server_configs(self) -> None:
        """Test accessing individual server configurations."""
        config = MCPServersConfig(mcpServers={
            "tool_server": ServerConfig(
                command="python",
                args=["-m", "tool_server"]
            ),
            "resource_server": ServerConfig(
                command="python",
                args=["-m", "resource_server"]
            )
        })

        tool_config = config.mcpServers["tool_server"]
        assert tool_config.command == "python"
        assert tool_config.args == ["-m", "tool_server"]

        resource_config = config.mcpServers["resource_server"]
        assert resource_config.command == "python"
        assert resource_config.args == ["-m", "resource_server"]

    def test_iteration_over_servers(self) -> None:
        """Test iterating over server configurations."""
        config = MCPServersConfig(mcpServers={
            "server1": ServerConfig(command="python", args=[]),
            "server2": ServerConfig(command="node", args=[]),
            "server3": ServerConfig(command="ruby", args=[])
        })

        server_names = list(config.mcpServers.keys())
        assert len(server_names) == 3
        assert "server1" in server_names
        assert "server2" in server_names
        assert "server3" in server_names
