"""Migration 1, on a vault written by teach-me 0.2 (tests/fixtures/teach_me_v0_vault, made by the tools of that version)."""

import shutil
from pathlib import Path

import pytest

from teach_me.database import migrations, objects, vault
from teach_me.tools import migrate_vault

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


def test_migrating_twice_changes_nothing(migrated):
    assert migrate_vault()["changes"] == []
