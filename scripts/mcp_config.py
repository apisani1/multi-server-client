#!/usr/bin/env python3
"""
Python script to generate MCP server configuration.
Handles file paths with spaces properly.
"""

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import (
    Any,
    Dict,
    Optional,
)


def extract_server_name(filepath: Path) -> Optional[str]:
    """Extract server name from FastMCP() pattern in the file."""
    try:
        content = filepath.read_text(encoding="utf-8")
        # Look for FastMCP("servername") pattern
        pattern = r'FastMCP\(["\']([^"\']*)["\']'
        match = re.search(pattern, content)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None


def create_or_update_config(server_name: str, filename: str, config_file: Path) -> bool:
    """Create or update the MCP configuration file."""
    try:
        # Create default config if file doesn't exist
        if not config_file.exists():
            default_config: Dict[str, Any] = {"mcpServers": {}}
            config_file.write_text(json.dumps(default_config, indent=2))

        # Load existing config
        config_data = json.loads(config_file.read_text(encoding="utf-8"))

        # Ensure mcpServers exists
        if "mcpServers" not in config_data:
            config_data["mcpServers"] = {}

        # Convert filename to module name (remove .py extension)
        module_name = filename.replace(".py", "")

        # Add server configuration using module calling approach
        config_data["mcpServers"][server_name] = {
            "command": "/Users/antonio/.local/bin/poetry",
            "args": [
                "run",
                "--directory",
                "/Users/antonio/Desktop/AI/MyCode/multi-server-client",
                "python3",
                "-m",
                f"src.mcp_multi_servert.{module_name}",
            ],
        }

        # Write updated config using a temporary file for atomic operation
        with tempfile.NamedTemporaryFile(mode="w", dir=config_file.parent, delete=False) as tmp:
            json.dump(config_data, tmp, indent=2)
            tmp_path = Path(tmp.name)

        # Atomically replace the original file
        tmp_path.replace(config_file)

        return True
    except Exception as e:
        print(f"Error updating config file {config_file}: {e}")
        return False


def main() -> None:
    """Main function to handle command line arguments and execute the script."""
    if len(sys.argv) < 2:
        print("Usage: python3 mcp_config.py <filename> [config_file]")
        print("  filename:    Python file containing FastMCP server")
        print("  config_file: JSON config file to update (default: mcp_server_config.json)")
        sys.exit(1)

    filename = sys.argv[1]
    config_file_name = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "/Users/antonio/Library/Application Support/Claude/claude_desktop_config.json"
    )

    # Construct the full path to the source file
    src_path = Path("src/mcp_multi_servert") / filename

    # Check if source file exists
    if not src_path.exists():
        print(f"Error: File {src_path} not found")
        sys.exit(1)

    # Extract server name from the file
    server_name = extract_server_name(src_path)
    if not server_name:
        print(f'Error: Could not find FastMCP("<servername>") pattern in {filename}')
        sys.exit(1)

    # Create or update config file
    config_file = Path(config_file_name)
    if create_or_update_config(server_name, filename, config_file):
        print(f"Added MCP server configuration for '{server_name}' using '{filename}' to {config_file}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
