import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import correct_exam, create_exam, get_course_state, read_exam

QUIZ = "# Convolution quiz\n\n### Question 1\n\n- [ ] A\n- [ ] B\n"


def test_exam_lifecycle(course, vault):
    path = create_exam(course, "Convolution quiz", "quiz", QUIZ, ["convolution"], project="pet-classifier")
    slug = path.rsplit("/", 1)[-1][:-3]
    exam = vault_io.read(vault / path)
    assert exam.metadata["status"] == "assigned"
    assert exam.metadata["project"] == "[[pet-classifier]]"
    assert exam.metadata["skills"] == [{"name": "convolution", "mark": None, "comment": None}]
    assert get_course_state(course)["pending_exams"][0]["slug"] == slug

    # The student fills the file
    (vault / path).write_text(
        (vault / path).read_text(encoding="utf-8").replace("- [ ] A", "- [x] A"), encoding="utf-8"
    )
    read = read_exam(slug)
    assert read["status"] == "filled"
    assert "- [x] A" in read["content"]

    result = correct_exam(slug, "# Corrected", {"convolution": 66}, ["correct", "correct", "incomplete"], {"convolution": "Forgot the flip"})
    assert result == {"correct": 0.67, "incomplete": 0.33, "wrong": 0.0, "marks": {"convolution": 66}}
    exam = vault_io.read(vault / path)
    assert exam.metadata["status"] == "corrected"
    assert exam.metadata["skills"] == [{"name": "convolution", "mark": 66, "comment": "Forgot the flip"}]
    assert exam.body.startswith("# Convolution quiz\n\n### Question 1\n\n- [x] A")  # the exam is kept
    assert exam.body.endswith("# Corrected")
    assert "## ✅ Correction (" in exam.body

    state = get_course_state(course)
    assert state["pending_exams"] == []
    assert {s["name"]: s["latest_mark"] for s in state["skills"]} == {"convolution": 66, "cnn-architecture": None}
    assert "corrected : 2 correct, 1 incomplete, 0 wrong" in state["sessions"][0]["entries"]


def test_exam_skills_must_be_declared(course):
    with pytest.raises(ToolError, match="Declared skills : convolution, cnn-architecture"):
        create_exam(course, "Quiz", "quiz", QUIZ, ["backpropagation"])


def test_exam_type_must_be_valid(course):
    with pytest.raises(ToolError, match="Unknown exam type"):
        create_exam(course, "Quiz", "oral", QUIZ, ["convolution"])


def _exam(course):
    return create_exam(course, "Quiz", "quiz", QUIZ, ["convolution", "cnn-architecture"]).rsplit("/", 1)[-1][:-3]


def test_correction_needs_every_mark(course):
    with pytest.raises(ToolError, match="Missing : cnn-architecture"):
        correct_exam(_exam(course), "# Corrected", {"convolution": 50}, ["correct"])


def test_correction_rejects_unknown_skills_and_invalid_marks(course):
    slug = _exam(course)
    with pytest.raises(ToolError, match="doesn't evaluate : nope"):
        correct_exam(slug, "# C", {"convolution": 50, "cnn-architecture": 50, "nope": 1}, ["correct"])
    with pytest.raises(ToolError, match="between 0 and 100"):
        correct_exam(slug, "# C", {"convolution": 150, "cnn-architecture": 50}, ["correct"])
    with pytest.raises(ToolError, match="Invalid outcomes"):
        correct_exam(slug, "# C", {"convolution": 50, "cnn-architecture": 50}, ["maybe"])


def test_latest_mark_follows_the_exams(course):
    first = create_exam(course, "Quiz 1", "quiz", QUIZ, ["convolution"]).rsplit("/", 1)[-1][:-3]
    second = create_exam(course, "Quiz 2", "quiz", QUIZ, ["convolution"]).rsplit("/", 1)[-1][:-3]
    correct_exam(first, "# C", {"convolution": 40}, ["wrong"])
    correct_exam(second, "# C", {"convolution": 80}, ["correct"])
    assert objects.mark_history(course) == {"convolution": [40, 80]}


def test_unknown_exam(course):
    with pytest.raises(ToolError, match="Unknown exam"):
        read_exam("nope")


def test_correction_never_removes_content(course, vault):
    path = create_exam(course, "Quiz", "quiz", QUIZ, ["convolution"])
    slug = path.rsplit("/", 1)[-1][:-3]
    correct_exam(slug, "## Correction\n\n1. A was right", {"convolution": 50}, ["correct"])
    correct_exam(slug, "1. After the retake, B was right too", {"convolution": 80}, ["correct"])  # a second correction
    body = vault_io.read(vault / path).body
    assert body.startswith(QUIZ.strip())
    assert body.count("## ✅ Correction (") == 2  # the model's own heading is replaced by the tool's
    assert body.index("A was right") < body.index("B was right too")
