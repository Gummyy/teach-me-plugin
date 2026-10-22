"""Structured arguments shared by several tools.

FastMCP turns these TypedDicts into JSON schemas, so the model knows exactly which keys to send.
"""

from typing_extensions import TypedDict  # typing.TypedDict isn't supported by pydantic before Python 3.12


class SkillDeclaration(TypedDict):
    """A skill, as declared for a course or already known by a user."""

    name: str
    """Short identifier of the skill, e.g. 'convolution'"""
    description: str
    """One sentence about what the student can do once the skill is validated"""
