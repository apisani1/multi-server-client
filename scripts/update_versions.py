#!/usr/bin/env python3
import re
import sys
from pathlib import Path

import toml  # type: ignore[import-untyped]


def update_files(new_version: str, dry_run: bool = False) -> None:
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        print("Error: pyproject.toml not found.")
        sys.exit(1)

    data = toml.load(pyproject)
    try:
        version_variables = data["tool"]["semantic_release"]["version_variable"]
    except KeyError:
        print("Error: [tool.semantic_release].version_variable not found.")
        sys.exit(1)

    for entry in version_variables:
        file_path, var_name = entry.split(":")
        path = Path(file_path)
        if not path.exists():
            print(f"Warning: {file_path} does not exist, skipping.")
            continue

        content = path.read_text()
        pattern = rf'{re.escape(var_name)}\s*=\s*["\']([^"\']+)["\']'
        if not re.search(pattern, content):
            print(f"Warning: Pattern for {var_name} not found in {file_path}, skipping.")
            continue

        new_line = f'{var_name} = "{new_version}"'
        new_content = re.sub(pattern, new_line, content)
        if dry_run:
            print(f"DRYRUN: {file_path}")
        else:
            path.write_text(new_content)
            print(f"UPDATED: {file_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: update_versions.py <version> [--dry-run]")
        sys.exit(1)

    version = sys.argv[1]
    dry = "--dry-run" in sys.argv
    update_files(version, dry)
