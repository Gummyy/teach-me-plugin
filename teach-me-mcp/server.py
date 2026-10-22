"""MCP server handling the persistent memory of the teach-me skill.

The memory is an Obsidian vault : a folder of markdown files, whose path is read from
the TEACH_ME_VAULT environment variable.

    python server.py      # stdio transport, launched by the MCP client
"""

from fastmcp import FastMCP

from teach_me.tools import ALL_TOOLS

mcp = FastMCP(
    name="teach-me",
    instructions=(
        "Persistent memory of the teach-me skill : users, projects, courses, sessions, classes, "
        "exams, shared resources and report cards, stored in the student's Obsidian vault. "
        "Objects are identified by their slug. Start every conversation with list_users, "
        "list_courses and get_course_state."
    ),
)

for tool in ALL_TOOLS:
    mcp.tool(tool)


if __name__ == "__main__":
    mcp.run()
