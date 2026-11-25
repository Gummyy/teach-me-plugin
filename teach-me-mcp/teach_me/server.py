"""MCP server handling the persistent memory of the teach-me skill.

The memory is an Obsidian vault : a folder of markdown files, whose path is read from
the TEACH_ME_VAULT environment variable.
"""

from fastmcp import FastMCP

from teach_me.database import migrations, vault
from teach_me.tools import ALL_TOOLS, migrate_vault, repair_note

WITHOUT_VERSION_CHECK = (migrate_vault, repair_note)
"""The tools that work on a vault of any version : the others refuse an older vault until it is migrated."""

mcp = FastMCP(
    name="teach-me",
    instructions=(
        "Persistent memory of the teach-me skill : users, projects, courses, sessions, classes, "
        "exams, shared resources and report cards, stored in the student's Obsidian vault. "
        "Objects are identified by their slug. Start every conversation with start_session. "
        "A result may hold `vault_warnings` : notes the tools skipped (broken by a hand edit) or found missing. "
        "Fix them as each warning says, without worrying the student, and keep working meanwhile."
    ),
)

for tool in ALL_TOOLS:
    checked = tool if tool in WITHOUT_VERSION_CHECK else migrations.requires_current(tool)
    mcp.tool(vault.serialized(vault.reporting(checked)))  # the lock of the vault : several sessions can share it


def main() -> None:
    """Entry point of the `teach-me-mcp` command : runs the server on the stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
