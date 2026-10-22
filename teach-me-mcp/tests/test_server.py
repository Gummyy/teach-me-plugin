"""Calls the tools through a real MCP client, connected in memory to the server."""

import asyncio

from fastmcp import Client

from server import mcp
from teach_me.tools import ALL_TOOLS


def run(coroutine):
    return asyncio.run(coroutine)


def test_every_tool_is_registered():
    async def scenario():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in run(scenario())}
    assert set(tools) == {tool.__name__ for tool in ALL_TOOLS}
    # The docstrings and type hints become what the model reads
    assert tools["create_course"].description is not None
    assert "Creates a course" in tools["create_course"].description
    skills = tools["create_course"].input_schema["properties"]["skills"]
    assert "skills" in tools["create_course"].input_schema["required"]
    assert skills["type"] == "array"


def test_journey_through_the_client(vault):
    async def scenario():
        async with Client(mcp) as client:
            await client.call_tool("create_user", {"name": "Alice"})
            users = await client.call_tool("list_users", {})
            failure = await client.call_tool("get_user", {"user": "bob"}, raise_on_error=False)
            return users, failure

    users, failure = run(scenario())
    assert users.data[0]["slug"] == "alice"
    assert failure.is_error
    assert "Known users : alice" in failure.content[0].text
