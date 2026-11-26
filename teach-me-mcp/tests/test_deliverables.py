import json

import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import create_deliverable, get_course_state, read_deliverable, read_exam
from tests.test_exams import _create

DATASET = {
    "title": "A dataset of pets",
    "text": "Collect pictures of your cats and dogs, sorted in one folder per class.",
    "skills": ["convolution"],
    "format": "folder of pictures",
    "criteria": ["At least 100 pictures per class", "One folder per class"],
    "expected_outcome": "Two balanced folders, pictures resized to 64x64.",
    "target_session": 1,
    "hints": ["How many pictures does a small CNN need ?", "Resize them all to the same size first."],
}
NETWORK = {
    "title": "A CNN that trains",
    "text": "Train a small CNN on your dataset.",
    "skills": ["cnn-architecture"],
    "format": "code",
    "criteria": ["The training loss decreases"],
    "expected_outcome": "2 convolution blocks, a dense layer with 2 outputs, a loss that decreases.",
    "target_session": 2,
    "hints": ["Start from 2 convolution blocks."],
}
REPORT = {
    "title": "A report on the results",
    "text": "Explain what your CNN learnt, with the feature maps of a picture.",
    "skills": ["convolution", "cnn-architecture"],
    "format": "report",
    "criteria": ["The feature maps of one picture are shown"],
    "expected_outcome": "Feature maps of each layer, commented.",
    "target_session": 3,
}
MILESTONES = [DATASET, NETWORK, REPORT]


def _deliverable(course, milestones=MILESTONES, max_sessions=3, **kwargs):
    arguments = {
        "title": "First CNN",
        "pitch": "Build a classifier for the pictures of your pets.",
        "outcome": "A CNN that tells my cats from my dogs, documented on GitHub",
        "project": "pet-classifier",
        "difficulty": "standard",
        "max_sessions": max_sessions,
        "milestones": list(milestones),
        "planned": "first-cnn",
        **kwargs,
    }
    return create_deliverable(course, **arguments)


def _write(vault, path, old, new):
    file = vault / path
    text = file.read_text(encoding="utf-8")
    assert old in text
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_create_deliverable_writes_the_subject_and_hides_the_outcomes(course, vault):
    created = _deliverable(course)
    assert created == {"slug": "first-cnn", "path": "courses/computer-vision/exams/deliverable-first-cnn.md", "milestones": 3, "max_sessions": 3, "warnings": []}
    document = vault_io.read(vault / created["path"])
    metadata = document.metadata
    assert metadata["type"] == "deliverable" and metadata["status"] == "assigned" and metadata["project"] == "[[project-pet-classifier]]"
    assert metadata["skills"] == ["[[skill-convolution]]", "[[skill-cnn-architecture]]"]
    assert (metadata["milestones"], metadata["milestones_done"], metadata["sessions"], metadata["max_sessions"]) == (3, 0, 0, 3)
    assert metadata["next_goal"] == "For check-in 1 : A dataset of pets" and metadata["difficulty"] == "standard" and metadata["mean"] is None
    body = document.body
    assert body.startswith("# First CNN") and "> [!example] 🎯 What you will have at the end\n> A CNN that tells my cats" in body
    assert "%% teach-me:roadmap start %%" in body and "| 2 | A CNN that trains | check-in 2 | ⏳ to do |" in body
    assert "## 🏁 Milestone 1 · A dataset of pets\n*Skill : [[skill-convolution|convolution]] · Format : folder of pictures · Due by check-in 1*" in body
    assert "- [ ] At least 100 pictures per class" in body and body.count("**Your work :**") == 3
    assert "balanced" not in body and "Start from 2" not in body  # the outcomes and the hints are hidden
    solutions = json.loads((vault / ".teach-me" / "solutions" / "first-cnn.json").read_text(encoding="utf-8"))
    assert solutions[1] == {"expected_outcome": NETWORK["expected_outcome"], "hints": NETWORK["hints"]} and solutions[2]["hints"] == []
    data = objects.exam_data("first-cnn")
    assert data["type"] == "deliverable" and data["questions"][0] == {
        "kind": "milestone", "skills": ["convolution"], "title": "A dataset of pets", "format": "folder of pictures", "target_session": 1, "status": "to do"
    }
    course_note = objects.get_course(course).body
    assert "Deliverable [[deliverable-first-cnn|First CNN]] assigned ([[project-pet-classifier]], 3 milestones, up to 3 check-ins)" in course_note
    assert "Deliverable 'First CNN' started" in objects.get_project("pet-classifier").body
    assert "first-cnn" not in [step["slug"] for step in get_course_state(course)["plan"]["next_steps"]]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"project": "nope"}, "doesn't build the project 'nope'"),
        ({"difficulty": "easy"}, "Unknown difficulty"),
        ({"max_sessions": 0}, "from 1 to 10"),
        ({"milestones": []}, "at least one milestone"),
        ({"milestones": [{**DATASET, "target_session": 4}]}, "Milestone 1 : `target_session` must be the check-in by which it should be done, from 1 to 3"),
        ({"milestones": [{**DATASET, "criteria": []}]}, "Milestone 1 needs `criteria`"),
        ({"milestones": [{**DATASET, "expected_outcome": ""}]}, "needs its `expected_outcome`"),
        ({"milestones": [{**DATASET, "skills": ["pooling"]}]}, "evaluates pooling, which the course doesn't declare"),
        ({"planned": "convolution-quiz"}, "'convolution-quiz' is a quiz, not a deliverable"),
    ],
)
def test_create_deliverable_checks_its_arguments(course, change, message):
    with pytest.raises(ToolError, match=message):
        _deliverable(course, **change)


def test_a_course_has_one_deliverable_at_a_time(course):
    _deliverable(course)
    with pytest.raises(ToolError, match="already has a deliverable in progress : 'first-cnn' \\(assigned\\)"):
        _deliverable(course, title="Second", planned=None)


def test_an_unplanned_deliverable_joins_the_plan(course, vault):
    created = _deliverable(course, planned=None, title="Pet detector")
    assert created["slug"] == "pet-detector" and "wasn't in the plan" in created["warnings"][0]
    assert "pass `planned` with one of the deliverable steps still to do : first-cnn" in created["warnings"][0]


def test_read_deliverable_returns_the_work_of_the_student(course, vault):
    path = _deliverable(course)["path"]
    _write(vault, path, "- [ ] One folder per class", "- [x] One folder per class")
    _write(vault, path, "**Your work :**", "**Your work :**\n\nMy pictures are in `data/` : [[nope-not-a-link]] 120 cats, 110 dogs.")
    view = read_deliverable("first-cnn")
    assert view["status"] == "assigned" and view["project"] == "pet-classifier" and view["difficulty"] == "standard"
    assert view["sessions"] == {"used": 0, "total": 3, "left": 3, "extended": False}
    first, second, _ = view["milestones"]
    assert first["criteria"] == [{"criterion": "At least 100 pictures per class", "done": False}, {"criterion": "One folder per class", "done": True}]
    assert first["work"].startswith("My pictures are in `data/`") and second["work"] is None
    assert first["expected_outcome"] == DATASET["expected_outcome"]
    assert first["hints"] == [{"hint": 1, "text": DATASET["hints"][0], "given": False}, {"hint": 2, "text": DATASET["hints"][1], "given": False}]
    assert view["checkins"] == [] and "# First CNN" in view["content"]


def test_quizzes_and_deliverables_have_their_own_tools(course):
    _deliverable(course)
    quiz = _create(course, planned="convolution-quiz")["slug"]
    with pytest.raises(ToolError, match="is a deliverable, not a quiz : use read_deliverable"):
        read_exam("first-cnn")
    with pytest.raises(ToolError, match="is a quiz, not a deliverable : use read_exam"):
        read_deliverable(quiz)


def test_a_plan_without_deliverable_is_warned(course):
    from teach_me.tools import create_course
    from tests.conftest import PLAN

    created = create_course("alice", "Subject", "", ["convolution", "cnn-architecture"], plan=PLAN[:3], projects=["pet-classifier"], name="Other")
    assert "The plan has no deliverable" in created["warnings"][0]
