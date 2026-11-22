"""Migration 1, on a vault written by teach-me 0.2 (tests/fixtures/teach_me_v0_vault, made by the tools of that version)."""

import shutil
from pathlib import Path

import pytest

from teach_me.database import migrations, objects, vault
from teach_me.tools import get_course_state, migrate_vault

FIXTURE = Path(__file__).parent / "fixtures" / "teach_me_v0_vault"


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    """The 0.2 vault, migrated. Returns the result of migrate_vault."""
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.setenv(vault.VAULT_ENV, str(tmp_path))
    assert migrations.vault_version() == 0
    return migrate_vault()


def note(relative: str):
    return vault.read(vault.vault_path() / relative)


def test_the_vault_is_at_the_current_version(migrated):
    assert migrated["from"] == 0 and migrated["to"] == migrations.current_version()
    migrations.check_current()


def test_every_note_has_a_type(migrated):
    assert note("users/user-alice.md").metadata["type"] == "user"
    assert note("projects/project-pet-classifier.md").metadata["type"] == "project"
    assert note("skills/skill-convolution.md").metadata["type"] == "skill"
    course = note("courses/computer-vision/course-computer-vision.md")
    assert list(course.metadata)[0] == "type" and course.metadata["type"] == "course"
    lesson = note("courses/computer-vision/classes/class-convolution.md").metadata
    assert lesson["type"] == "class" and lesson["course"] == "[[course-computer-vision]]"
    exam = note("courses/computer-vision/exams/quiz-convolution-quiz.md")
    assert exam.metadata["type"] == "quiz" and objects.exam_type(exam) == "quiz"


def test_exams_are_flat(migrated):
    exam = note("courses/computer-vision/exams/quiz-convolution-quiz.md").metadata
    assert exam["skills"] == ["[[skill-convolution]]"] and exam["questions"] == 2 and exam["mean"] == 4.5
    data = objects.exam_data("convolution-quiz")
    assert [question["grade"] for question in data["questions"]] == ["A", "B"]
    assert data["skills"] == {"convolution": {"grade": "A", "score": 4.5, "comment": "Good start."}}


def test_skill_notes_show_their_grade(migrated):
    skill = note("skills/skill-convolution.md")
    assert skill.metadata["description"] == "Computes and interprets a 2D convolution"
    assert skill.metadata["grade"] == "A" and skill.metadata["evaluations"] == 1 and skill.metadata["progression"] == "A"
    assert "| A | 4.5/5 | Good start. |" in skill.body and skill.body.endswith("## ✏️ My notes")
    untouched = note("skills/skill-cnn-architecture.md")
    assert untouched.metadata["grade"] is None and "Not evaluated yet" in untouched.body


def test_each_step_of_the_plan_is_a_note(migrated):
    course = note("courses/computer-vision/course-computer-vision.md")
    assert "plan" not in course.metadata and "## Plan" not in course.body
    assert course.body.startswith("%% teach-me:dashboard start %%") and course.body.index("## ✏️ My notes") < course.body.index("- Course created")
    expected = [
        ("classes/class-convolution.md", 1, "done", "Kernels and feature maps"),
        ("exams/quiz-convolution-quiz.md", 2, "corrected", ""),
        ("classes/class-pooling.md", 3, "done", "Max pooling."),
        ("classes/class-cnn-architectures.md", 4, "planned", ""),
        ("exams/exercise-first-cnn.md", 5, "planned", "Train a CNN on the pictures"),
    ]
    for path, order, status, description in expected:
        metadata = note(f"courses/computer-vision/{path}").metadata
        assert (metadata["order"], metadata["status"], metadata["description"]) == (order, status, description), path
    lesson = note("courses/computer-vision/classes/class-convolution.md").metadata
    assert "summary" not in lesson and lesson["started_at"] == lesson["created_at"]
    assert lesson["suggested_resources"] == ["3Blue1Brown on convolutions"] and lesson["skills"] == ["[[skill-convolution]]"]
    assert note("courses/computer-vision/classes/class-pooling.md").metadata["added"] is True
    assert note("courses/computer-vision/exams/exercise-first-cnn.md").metadata["type"] == "exercise"
    assert get_course_state("computer-vision")["plan"]["done"] == 3


def test_a_course_of_teach_me_0_1(tmp_path, monkeypatch):
    """Before the plans, a course listed its classes and exams in a "## Content" section."""
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.setenv(vault.VAULT_ENV, str(tmp_path))
    course = note("courses/computer-vision/course-computer-vision.md")
    del course.metadata["plan"]
    start, end = course.body.index("## Plan"), course.body.index("## 20")
    course.body = course.body[:start] + "## Content\n\n1. Class : [[class-convolution|Convolution]]\n\n" + course.body[end:]
    vault.write(course)
    migrate_vault()
    steps = get_course_state("computer-vision")["plan"]
    assert steps["total"] == 3  # the class of the content, then the documents it didn't list
    assert note("courses/computer-vision/classes/class-convolution.md").metadata["order"] == 1
    assert "## Content" not in note("courses/computer-vision/course-computer-vision.md").body


def test_resources_are_notes(migrated):
    assert "resources" not in note("courses/computer-vision/course-computer-vision.md").metadata
    video = note("courses/computer-vision/resources/resource-3blue1brown-but-what-is-a-convolution.md").metadata
    assert video["type"] == "resource" and video["url"] == "https://www.youtube.com/watch?v=KuXjwB4LzSA" and video["status"] == "new"
    old = note("courses/computer-vision/resources/resource-old-notes.md").metadata
    assert old["file"] == "notes.pdf" and old["status"] == "dropped"  # was unprocessed
    assert [r["slug"] for r in get_course_state("computer-vision")["new_resources"]] == ["3blue1brown-but-what-is-a-convolution"]


def test_migrating_twice_changes_nothing(migrated):
    assert migrate_vault()["changes"] == []
