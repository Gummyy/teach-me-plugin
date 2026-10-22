"""Runs the teach-me MCP server without installing it : `python server.py`

Once installed (`pip install .` or `uv run`), the same server is the `teach-me-mcp` command.
"""

from teach_me.server import main, mcp  # noqa: F401  (mcp is exposed for the MCP Inspector)

if __name__ == "__main__":
    main()
