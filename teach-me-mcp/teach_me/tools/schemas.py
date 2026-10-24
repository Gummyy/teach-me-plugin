"""Structured arguments shared by several tools.

FastMCP turns these TypedDicts into JSON schemas, so the model knows exactly which keys to send.
"""

from typing import Literal

from typing_extensions import NotRequired, TypedDict  # typing.TypedDict isn't supported by pydantic before Python 3.12

Outcome = Literal["correct", "incomplete", "wrong"]
QuestionKind = Literal["open", "single", "multiple"]


class SkillDeclaration(TypedDict):
    """A skill, as declared for a course or already known by a user."""

    name: str
    """Short identifier of the skill, e.g. 'convolution'"""
    description: str
    """One sentence about what the student can do once the skill is validated"""


class Question(TypedDict):
    """A question of an exam."""

    kind: QuestionKind
    """open : the student writes the answer. single : exactly one correct option. multiple : one or more correct options"""
    text: str
    """The question, in markdown (formulas, code and diagrams are welcome)"""
    skill: str
    """The name of the skill it evaluates, declared in the course"""
    options: NotRequired[list[str]]
    """Closed questions only : the options, 2 to 8, labelled A, B, C, ... in this order"""
    correct_options: NotRequired[list[str]]
    """Closed questions only : the letters of the correct options, e.g. ["B"] or ["A", "C"]. Hidden from the student"""
    expected_answer: NotRequired[str]
    """Open questions only : what a good answer contains, used to correct it. Hidden from the student"""


class QuestionCorrection(TypedDict):
    """The correction of one question."""

    explanation: str
    """Why the right answer is right, and what the student missed, in markdown"""
    outcome: NotRequired[Outcome]
    """Open questions only (required for them) : the closed questions are graded by the server"""
