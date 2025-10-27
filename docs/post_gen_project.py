# hooks/post_gen_project.py
import os
import subprocess


# Create API documentation structure
os.makedirs("docs/api", exist_ok=True)

try:
    subprocess.run(["sphinx-apidoc", "-o", "docs/api", "src/multi_server_client"], check=True)
except Exception as e:
    print(f"Note: Could not auto-generate API docs: {e}")
    # Create placeholder file
    with open("docs/api/modules.rst", "w") as f:
        f.write(
            "API Reference\n=============\n\n.. toctree::\n   :maxdepth: 4\n\n   multi_server_client\n"
        )
