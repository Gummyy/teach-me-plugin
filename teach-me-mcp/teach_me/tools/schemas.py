"""Structured arguments shared by several tools.

FastMCP turns these TypedDicts into JSON schemas, so the model knows exactly which keys to send. The
docstring under each key becomes its description in the schema.
"""

from typing import Literal, Optional

from pydantic import ConfigDict, with_config
from typing_extensions import NotRequired, Required, TypedDict  # typing.TypedDict isn't supported by pydantic before Python 3.12

DOCUMENTED = ConfigDict(use_attribute_docstrings=True)
STRICT = ConfigDict(use_attribute_docstrings=True, extra="forbid")
"""For the preferences : an unknown key is refused instead of being silently dropped."""

Grade = Literal["A", "B", "C", "D", "E"]
QuestionKind = Literal["open", "single", "multiple"]


@with_config(STRICT)
class Preferences(TypedDict, total=False):
    """The preferences of a user that don't depend on the interface. A null value removes a preference."""

    language: Optional[str]
    """The language of the classes and exams, e.g. 'french'"""
    tone: Optional[str]
    """How to talk to the student, e.g. 'casual, with jokes'"""
    other: dict[str, Optional[str]]
    """Any other preference, by name, e.g. {"examples": "from biology"}. Stored next to the fields above"""


@with_config(STRICT)
class NewPreferences(TypedDict, total=False):
    """The preferences of a new user. The keys are the ones of Preferences, declared again because pydantic only reads the docstrings of the class itself."""

    language: Required[str]
    """The language of the classes and exams : the one the student talks to you in, unless they said otherwise"""
    tone: str
    """How to talk to the student, e.g. 'casual, with jokes'"""
    other: dict[str, str]
    """Any other preference, by name, e.g. {"examples": "from biology"}. Stored next to the fields above"""


@with_config(STRICT)
class InterfacePreferences(TypedDict, total=False):
    """The preferences of a user for one interface. A null value removes a preference."""

    quizzes: Optional[Literal["chat", "vault"]]
    """Where quizzes are given and answered : in the chat, or in a file of the vault"""
    diagrams: Optional[Literal["rendered", "raw", "avoid"]]
    """How mermaid diagrams show : rendered, shown as raw text (still readable in the vault), or to avoid"""
    other: dict[str, Optional[str]]
    """Any other preference for this interface, by name. Stored next to the fields above"""


@with_config(DOCUMENTED)
class SkillDeclaration(TypedDict):
    """A skill, as declared for a course or already known by a user."""

    name: str
    """Short identifier of the skill, e.g. 'convolution'"""
    description: str
    """One sentence about what the student can do once the skill is validated"""


@with_config(DOCUMENTED)
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


@with_config(DOCUMENTED)
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
