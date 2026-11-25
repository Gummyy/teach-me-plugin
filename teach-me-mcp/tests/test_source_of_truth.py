"""The hidden data of an exam is the source of truth : what the student changes by hand in a grade, a mean, a status or
the type of an exam never changes the grades, and start_session writes the true values back."""

import json
import re

from teach_me.database import migrations, objects
from teach_me.database import vault as vault_io
from teach_me.tools import get_course_state, migrate_vault, start_session, submit_answers, correct_exam
from tests.test_exams import GRADES, _create

start = vault_io.reporting(start_session)


def _set(path, key, value):
    text = path.read_text(encoding="utf-8")
    changed = re.sub(rf"^{key}: .*$", f"{key}: {value}", text, count=1, flags=re.MULTILINE)
    assert changed != text
    path.write_text(changed, encoding="utf-8")


def _corrected(course, vault, type="quiz", planned="convolution-quiz"):
    exam = _create(course, type=type, planned=planned)
    submit_answers(exam["slug"], ["A", "A, B", "Convolutions then a dense layer"])
    correct_exam(exam["slug"], GRADES)
    return exam["slug"], vault / exam["path"]


def _grades():
    return {skill: (grade["grade"], grade["score"]) for skill, grade in objects.skill_grades("alice").items()}


def test_changing_the_status_of_an_exam_changes_no_grade(course, vault):
    exam, path = _corrected(course, vault)
    before = _grades()
    for status in ("assigned", "planned", "dropped"):
        _set(path, "status", status)
        assert _grades() == before
        assert objects.exam_status(vault_io.read(path)) == "corrected"
    assert get_course_state(course)["pending_exams"] == []
    result = start("terminal", "alice", course)
    assert vault_io.read(path).metadata["status"] == "corrected"
    assert any("Restored" in warning and exam in warning for warning in result["vault_warnings"])


def test_changing_the_type_of_an_exam_changes_no_grade(course, vault):
    exam, path = _corrected(course, vault)
    before = _grades()
    _set(path, "type", "exercise")
    assert _grades() == before
    start("terminal", "alice", course)
    assert vault_io.read(path).metadata["type"] == "quiz"


def test_a_grade_or_a_mean_changed_by_hand_is_restored(course, vault):
    exam, path = _corrected(course, vault)
    skill = objects.skill_file("cnn-architecture")
    _set(skill, "grade", "A")
    _set(skill, "score", "5.0")
    mean = vault_io.read(path).metadata["mean"]
    _set(path, "mean", "5.0")
    start("terminal", "alice", course)
    assert vault_io.read(skill).metadata["grade"] == "B" and vault_io.read(skill).metadata["score"] == 4.0
    assert vault_io.read(path).metadata["mean"] == mean


def test_the_hidden_data_holds_the_type_and_is_written_first(course, vault):
    exam, _ = _corrected(course, vault, type="project", planned="first-cnn")
    data = objects.exam_data(exam)
    assert data["type"] == "project" and data["corrected_at"]


def test_a_retake_counts_once_corrected_again(course, vault):
    exam, path = _corrected(course, vault)
    submit_answers(exam, ["B", "A", "Only dense layers"])
    assert vault_io.read(path).metadata["status"] == "filled"
    assert _grades() == {}
    correct_exam(exam, GRADES)
    assert vault_io.read(path).metadata["status"] == "corrected" and _grades()


def test_a_healthy_vault_is_not_rewritten(course, vault):
    _corrected(course, vault)
    start("terminal", "alice", course)
    assert "vault_warnings" not in start("terminal", "alice", course)


def test_migration_3_gives_the_exams_their_type(course, vault):
    exam, path = _corrected(course, vault, type="project", planned="first-cnn")
    file = objects.exam_data_file(exam)
    data = json.loads(file.read_text(encoding="utf-8"))
    del data["type"]
    file.write_text(json.dumps(data), encoding="utf-8")
    _set(path, "status", "assigned")
    (vault / ".teach-me" / "version").write_text("2\n")
    result = migrate_vault()
    assert result["to"] == migrations.current_version() == 3
    assert objects.exam_data(exam)["type"] == "project"
    assert vault_io.read(path).metadata["status"] == "corrected"
    assert any(change.endswith(": type") for change in result["changes"])
