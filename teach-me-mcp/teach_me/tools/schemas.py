"""Structured arguments shared by several tools.

FastMCP turns these TypedDicts into JSON schemas, so the model knows exactly which keys to send.
"""

from typing import Literal

from typing_extensions import NotRequired, TypedDict  # typing.TypedDict isn't supported by pydantic before Python 3.12

Grade = Literal["A", "B", "C", "D", "E"]
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
    skills: list[str]
    """The slugs of the skills it evaluates, among the skills of the course. The grade of the question counts for each of them"""
    options: NotRequired[list[str]]
    """Closed questions only : the options, 2 to 8, labelled A, B, C, ... in this order"""
    correct_options: NotRequired[list[str]]
    """Closed questions only : the letters of the correct options, e.g. ["B"] or ["A", "C"]. Hidden from the student"""
    expected_answer: NotRequired[str]
    """Open questions only : what a good answer contains, used to correct it. Hidden from the student"""


class QuestionGrade(TypedDict):
    """The grade of a question.

    A : correct, solves all the problems raised by the question (5).
    B : solves the main problems but misses some important aspects (4).
    C : incomplete, doesn't solve the main problem (2).
    D : wrong, doesn't answer the question (1).
    E : no answer (0), given by the server to every unanswered question.
    """

    question: int
    """The number of the question, starting at 1"""
    explanation: str
    """Why the right answer is right, and what the student did well or missed, in markdown"""
    grade: NotRequired[Grade]
    """Required for open questions. For closed questions, leave it out to accept the grade proposed by read_exam"""
