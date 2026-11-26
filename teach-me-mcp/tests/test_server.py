"""Calls the tools through a real MCP client, connected in memory to the server."""

import asyncio

from fastmcp import Client

from teach_me.server import mcp
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
            await client.call_tool("create_user", {"name": "Alice", "preferences": {"language": "english"}})
            refused = await client.call_tool("create_user", {"name": "Bob", "preferences": {"language": "english", "quizzes": "chat"}}, raise_on_error=False)
            users = await client.call_tool("list_users", {})
            failure = await client.call_tool("get_user", {"user": "bob"}, raise_on_error=False)
            return users, failure, refused

    users, failure, refused = run(scenario())
    assert refused.is_error  # an unknown key of the preferences is refused, not silently dropped
    assert users.data[0]["slug"] == "alice"
    assert failure.is_error
    assert "Known users : alice" in failure.content[0].text


def test_a_planned_course_through_the_client(vault):
    step = {"kind": "class", "title": "Kernels", "description": "What a kernel is", "skills": ["convolution"], "importance": "core"}
    quiz = {"kind": "quiz", "title": "Kernels quiz", "description": "", "skills": ["convolution"], "importance": "core"}
    question = {"kind": "open", "text": "What is a kernel ?", "skills": ["convolution"], "expected_answer": "A small matrix"}

    async def scenario():
        async with Client(mcp) as client:
            await client.call_tool("create_user", {"name": "Alice", "preferences": {"language": "english"}})
            await client.call_tool("create_skills", {"user": "alice", "skills": [{"name": "convolution", "description": "Computes a convolution"}]})
            created = await client.call_tool("create_course", {"user": "alice", "subject": "Vision", "starting_level": "", "skills": ["convolution"], "plan": [step, quiz], "name": "Vision"})
            edited = await client.call_tool("edit_course", {"course": "vision", "update_steps": [{"step": "kernels-quiz", "move_after": "", "importance": "optional"}]})
            await client.call_tool("save_class", {"course": "vision", "title": "Kernels", "summary": "", "content": "A class", "planned": "kernels"})
            await client.call_tool("update_class", {"course": "vision", "slug": "kernels", "status": "read"})
            exam = await client.call_tool("create_exam", {"course": "vision", "title": "Kernels quiz", "type": "quiz", "questions": [question], "planned": "kernels-quiz"})
            await client.call_tool("submit_answers", {"exam": "kernels-quiz", "answers": ["A small matrix"]})
            corrected = await client.call_tool("correct_exam", {"exam": "kernels-quiz", "grades": [{"question": 1, "grade": "A", "explanation": "Right"}]})
            state = await client.call_tool("get_course_state", {"course": "vision"})
            return created, edited, exam, corrected, state

    created, edited, exam, corrected, state = run(scenario())
    assert [s["slug"] for s in created.data["plan"]] == ["kernels", "kernels-quiz"]
    assert [s["slug"] for s in edited.data["plan"]] == ["kernels-quiz", "kernels"]
    assert exam.data["warnings"] == [] and corrected.data["grades"] == ["A"]
    assert state.data["plan"]["done"] == 2 and state.data["plan"]["next_steps"] == []
    assert not (vault / ".teach-me" / "lock").exists()
