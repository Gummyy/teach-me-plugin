import json
from datetime import datetime, timedelta

import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import checkin_deliverable, correct_deliverable, create_deliverable, get_course_state, read_deliverable, read_exam, report_card
from tests.test_exams import GRADES, _correct, _create, _grades

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


@pytest.fixture
def clock(monkeypatch):
    """The time of the tools, moved to the next session with `clock.next()`."""

    class Clock:
        moment = datetime(2026, 11, 26, 14, 0)

        def next(self, hours=24):
            self.moment += timedelta(hours=hours)

    found = Clock()
    monkeypatch.setattr(vault_io, "now", lambda: found.moment)
    return found


FEEDBACK = {"milestone": 1, "status": "in progress", "feedback": "Good start : 60 pictures of cats, the dogs are missing."}


def _checkin(slug="first-cnn", milestones=(FEEDBACK,), next_goals="Finish the dataset.", **kwargs):
    return checkin_deliverable(slug, "The folder of pictures.", list(milestones), next_goals, **kwargs)


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


def test_a_checkin_gives_feedback_and_counts_a_session(clock, course, vault):
    path = vault / _deliverable(course)["path"]
    result = _checkin(hints=[{"milestone": 1, "hint": 2}])
    assert result["checkin"] == 1 and result["status"] == "in progress"
    assert result["sessions"] == {"used": 1, "total": 3, "left": 2} and result["milestones_done"] == 0
    assert "Next check-in at the next session" in result["next_step"]
    document = vault_io.read(path)
    assert document.metadata["status"] == "in progress" and document.metadata["sessions"] == 1
    assert document.metadata["next_goal"] == "Finish the dataset." and document.metadata["last_checkin"] == "2026-11-26T14:00"
    body = document.body
    assert "## 📅 Check-ins\n\n### Check-in 1 · 2026-11-26 14:00" in body and "**What you showed :** The folder of pictures." in body
    assert "> [!note] Milestone 1 · A dataset of pets : 🔨 in progress\n> Good start" in body
    assert f"> [!tip] Hint for milestone 1\n> {DATASET['hints'][1]}" in body  # the hint is written for the student
    assert "| 1 | A dataset of pets | check-in 1 | 🔨 in progress |" in body and "**Next goal :** Finish the dataset." in body
    assert body.index("## 🏁 Milestone 3") < body.index("## 📅 Check-ins")
    assert read_deliverable("first-cnn")["milestones"][0]["hints"][1]["given"] is True
    assert "Check-in 1/3 on the deliverable [[deliverable-first-cnn|First CNN]] : 0/3 milestones done, 1 hint(s) given" in objects.get_course(course).body
    assert "Check-in 1 on 'First CNN' : 0/3 milestones done" in objects.get_project("pet-classifier").body


def test_checkins_of_one_session_count_once(clock, course, vault):
    _deliverable(course)
    _checkin()
    clock.next(hours=1)
    again = _checkin(milestones=[{**FEEDBACK, "status": "done"}])
    assert again["sessions"]["used"] == 1 and again["checkin"] == 1 and again["milestones_done"] == 1
    clock.next()
    assert _checkin(milestones=[{**FEEDBACK, "milestone": 2}])["sessions"]["used"] == 2
    body = vault_io.read(vault / "courses/computer-vision/exams/deliverable-first-cnn.md").body
    assert body.count("### Check-in 1 ·") == 2 and body.count("### Check-in 2 ·") == 1  # appended, never rewritten


def test_the_last_session_submits_the_deliverable(clock, course, vault):
    _deliverable(course, max_sessions=2, milestones=[DATASET, {**NETWORK, "target_session": 2}])
    _checkin()
    clock.next()
    last = _checkin()
    assert last["status"] == "submitted" and "grade it now with correct_deliverable" in last["next_step"] and "extend it once" in last["next_step"]
    clock.next(hours=1)
    assert _checkin()["status"] == "submitted"  # the same session : one more check-in is fine
    clock.next()
    with pytest.raises(ToolError, match="Every session of the deliverable 'first-cnn' is used"):
        _checkin()
    extended = _checkin(extend=1, reschedule=[{"milestone": 2, "target_session": 3}])
    assert extended["status"] == "submitted" and extended["sessions"] == {"used": 3, "total": 3, "left": 0}
    assert "It was already extended" in extended["next_step"]
    body = vault_io.read(vault / "courses/computer-vision/exams/deliverable-first-cnn.md").body
    assert "- 1 more session : up to 3 check-ins" in body and "- Milestone 2 · A CNN that trains : due by check-in 2 → 3" in body
    clock.next()
    with pytest.raises(ToolError, match="already extended once"):
        _checkin(extend=1)


def test_every_milestone_done_asks_for_the_grading(clock, course):
    _deliverable(course, milestones=[DATASET])
    result = _checkin(milestones=[{**FEEDBACK, "status": "done"}])
    assert result["status"] == "in progress" and "Every milestone is done" in result["next_step"]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"milestones": []}, "at least one milestone"),
        ({"milestones": [{**FEEDBACK, "milestone": 4}]}, "from 1 to 3, not 4"),
        ({"milestones": [FEEDBACK, FEEDBACK]}, "given twice"),
        ({"milestones": [{**FEEDBACK, "status": "finished"}]}, "needs a `status`"),
        ({"milestones": [{**FEEDBACK, "feedback": " "}]}, "has no `feedback`"),
        ({"next_goals": ""}, "needs `shown`"),
        ({"hints": [{"milestone": 1, "hint": 3}]}, "has 2 hint\\(s\\) : `hint` must be from 1 to 2"),
        ({"hints": [{"milestone": 3, "hint": 1}]}, "Milestone 3 has no hint"),
        ({"reschedule": [{"milestone": 1, "target_session": 4}]}, "Extend the deliverable"),
        ({"extend": 4}, "from 1 to 3"),
    ],
)
def test_checkin_checks_its_arguments(clock, course, change, message):
    _deliverable(course)
    with pytest.raises(ToolError, match=message):
        _checkin(**change)
    assert objects.exam_data("first-cnn")["checkins"] == []  # nothing written


def test_a_checkin_goes_before_my_notes_and_after_the_other_checkins():
    from teach_me.database import deliverable

    body = "# T\n\n## 🏁 Milestone 1 · A\n\n**Your work :**\n\nDone.\n\n## ✏️ My notes\n\nMine."
    once = deliverable.add_checkin(body, "### Check-in 1")
    assert once == "# T\n\n## 🏁 Milestone 1 · A\n\n**Your work :**\n\nDone.\n\n## 📅 Check-ins\n\n### Check-in 1\n\n## ✏️ My notes\n\nMine."
    twice = deliverable.add_checkin(once, "### Check-in 2")
    assert twice.index("### Check-in 1") < twice.index("### Check-in 2") < twice.index("## ✏️ My notes")
    assert deliverable.parse_work(twice, 1)[0]["work"] == "Done."


SHOWCASE = "A CNN that tells my cats from my dogs, 90 % accurate"


def _grade(milestone, grade):
    return {"milestone": milestone, "grade": grade, "explanation": f"Explanation {milestone}."}


def test_correct_deliverable_grades_the_milestones_once(clock, course, vault):
    path = vault / _deliverable(course)["path"]
    _checkin()
    result = correct_deliverable("first-cnn", [_grade(1, "A"), _grade(2, "B"), _grade(3, "abandoned")], SHOWCASE, {"convolution": "Clean dataset"})
    assert result == {
        "status": "corrected",
        "grades": ["A", "B", "abandoned"],
        "mean": 4.5,
        "skills": {"convolution": {"grade": "A", "score": 5.0}, "cnn-architecture": {"grade": "B", "score": 4.0}},
        "showcase": SHOWCASE,
    }
    document = vault_io.read(path)
    assert (document.metadata["status"], document.metadata["mean"], document.metadata["showcase"]) == ("corrected", 4.5, SHOWCASE)
    body = document.body
    assert "## ✅ Correction (2026-11-26 14:00)\n\n**1** A, **1** B, **1** abandoned · mean **4.5/5**" in body
    assert f"> [!example] 🎓 For your resume\n> {SHOWCASE}" in body
    assert "> [!Abstract] Milestone 3 · A report on the results : abandoned, not graded" in body and REPORT["expected_outcome"] in body
    assert "| Grade |" in body and "| 2 | A CNN that trains | check-in 2 | ⏳ to do | B |" in body and "**Next goal :**" not in body
    assert body.index("## 📅 Check-ins") < body.index("## ✅ Correction")
    assert _grades("alice") == {"convolution": {"grade": "A", "score": 5.0, "history": ["A"]}, "cnn-architecture": {"grade": "B", "score": 4.0, "history": ["B"]}}
    assert "| Clean dataset |" in objects.skill_file("convolution").read_text(encoding="utf-8")
    assert "Deliverable [[deliverable-first-cnn|First CNN]] corrected : 1 A, 1 B, 1 abandoned (mean 4.5/5)" in objects.get_course(course).body
    assert f"Deliverable 'First CNN' corrected : {SHOWCASE}" in objects.get_project("pet-classifier").body
    assert get_course_state(course)["plan"]["done"] == 1
    assert f"| corrected | 4.5/5 | {SHOWCASE} |" in report_card(course)
    with pytest.raises(ToolError, match="already corrected : a deliverable is graded once"):
        correct_deliverable("first-cnn", [_grade(1, "A"), _grade(2, "B"), _grade(3, "A")], SHOWCASE)
    with pytest.raises(ToolError, match="is corrected : it takes no more check-ins"):
        _checkin()


def test_half_of_the_milestones_abandoned_abandons_the_deliverable(clock, course, vault):
    path = vault / _deliverable(course, milestones=[DATASET, NETWORK])["path"]
    result = correct_deliverable("first-cnn", [_grade(1, "C"), _grade(2, "abandoned")])  # no showcase needed
    assert result["status"] == "abandoned" and result["mean"] is None and result["grades"] == ["C", "abandoned"]
    document = vault_io.read(path)
    assert document.metadata["status"] == "abandoned" and document.metadata["mean"] is None
    assert "the deliverable is **abandoned**" in document.body
    assert _grades("alice") == {"convolution": {"grade": "C", "score": 2.0, "history": ["C"]}}  # the milestone built still counts
    assert get_course_state(course)["plan"]["done"] == 1
    assert "| abandoned | — |" in report_card(course)


def test_a_milestone_weighs_three_questions_of_a_quiz(clock, course):
    quiz = _create(course, planned="convolution-quiz")["slug"]
    _correct(quiz, ["B", "A, B", "x"], GRADES)  # convolution : D and A
    _deliverable(course, milestones=[DATASET])
    correct_deliverable("first-cnn", [_grade(1, "A")], SHOWCASE)
    assert _grades("alice")["convolution"] == {"grade": "B", "score": 4.2, "history": ["B", "A"]}  # (1 + 5 + 3 x 5) / 5, 3.67 if it weighed 1


@pytest.mark.parametrize(
    "grades, showcase, message",
    [
        ([_grade(1, "A"), _grade(2, "B")], SHOWCASE, "milestone\\(s\\) 3 have no grade"),
        ([_grade(1, "A"), _grade(1, "B"), _grade(3, "A")], SHOWCASE, "graded twice"),
        ([_grade(1, "E"), _grade(2, "B"), _grade(3, "A")], SHOWCASE, "needs a `grade` among : A, B, C, D, abandoned"),
        ([{**_grade(1, "A"), "explanation": ""}, _grade(2, "B"), _grade(3, "A")], SHOWCASE, "has no `explanation`"),
        ([_grade(1, "A"), _grade(2, "B"), _grade(3, "A")], None, "Give the `showcase`"),
    ],
)
def test_correct_deliverable_checks_its_arguments(clock, course, grades, showcase, message):
    _deliverable(course)
    with pytest.raises(ToolError, match=message):
        correct_deliverable("first-cnn", grades, showcase)
    assert objects.exam_data("first-cnn")["corrected_at"] is None
