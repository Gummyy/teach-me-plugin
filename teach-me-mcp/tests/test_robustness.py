"""What the student can break by hand in Obsidian must never stop the tools : a broken note is skipped with a warning,
a missing note keeps its link, and the result tells the model in `vault_warnings`."""

import re

import pytest

from teach_me.database import objects, plan as plans
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import correct_exam, edit_course, get_course_state, read_exam, report_card, start_session, submit_answers
from tests.test_exams import GRADES, _create

start = vault_io.reporting(start_session)
state = vault_io.reporting(get_course_state)
edit = vault_io.reporting(edit_course)


def _edit(path, pattern, replacement):
    text = path.read_text(encoding="utf-8")
    changed = re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE)
    assert changed != text
    path.write_text(changed, encoding="utf-8")


def _corrected(course):
    exam = _create(course, planned="convolution-quiz")["slug"]
    submit_answers(exam, ["A", "A, B", "Convolutions then a dense layer"])
    correct_exam(exam, GRADES)
    return exam


def test_a_broken_step_is_skipped(course, vault):
    step = vault / "courses" / course / "classes" / "class-cnn-architectures.md"
    _edit(step, r"^title: .*$", "title: [oops")
    result = start("terminal", "alice", course)
    assert "cnn-architectures" not in [s["slug"] for s in result["course"]["plan"]["next_steps"]]
    assert any("class-cnn-architectures.md" in warning and "repair_note" in warning for warning in result["vault_warnings"])
    with pytest.raises(ToolError, match="repair_note"):
        vault_io.read(step)  # the note itself still says how to repair it


def test_a_deleted_project_doesnt_stop_the_session(course, vault):
    objects.project_file("pet-classifier").unlink()
    result = start("terminal", "alice", course)
    assert result["course"]["projects"] == []
    assert any("project-pet-classifier.md is missing" in warning for warning in result["vault_warnings"])
    assert "vault_warnings" in edit(course, name="Vision")
    assert "[[project-pet-classifier]]" in objects.get_course(course).metadata["projects"]


def test_a_deleted_skill_doesnt_stop_the_course(course, vault):
    exam = _create(course, planned="convolution-quiz")["slug"]
    objects.skill_file("cnn-architecture").unlink()
    result = state(course)
    assert [skill["slug"] for skill in result["skills"]] == ["convolution"]
    assert any("skill-cnn-architecture.md is missing" in warning for warning in result["vault_warnings"])
    assert "vault_warnings" in edit(course, name="Vision")
    assert "[[skill-cnn-architecture]]" in objects.get_course(course).metadata["skills"]
    submit_answers(exam, ["A", "A, B", "Convolutions then a dense layer"])
    assert correct_exam(exam, GRADES)["skills"]["cnn-architecture"]["grade"] == "B"
    assert "cnn-architecture" not in report_card(course)  # the report card lists the skills that have a note


def test_a_list_turned_into_a_text_is_still_a_list(course, vault):
    _edit(objects.course_file(course), r"^skills:\n(?:- .*\n)+", "skills: '[[skill-convolution]]'\n")
    assert objects.course_skills(objects.get_course(course)) == ["convolution"]
    assert objects.as_list(None) == [] and objects.as_list(["a", None, "", "b"]) == ["a", "b"]


def test_an_order_typed_as_text_is_still_a_number(course, vault):
    step = vault / "courses" / course / "classes" / "class-convolution.md"
    _edit(step, r"^order: 1$", "order: '9'")
    assert [s["slug"] for s in plans.course_plan(objects.get_course(course))][-1] == "convolution"


def test_a_broken_exam_data_file_is_skipped(course, vault):
    exam = _corrected(course)
    assert objects.skill_grades("alice")
    objects.exam_data_file(exam).write_text('{"questions": [', encoding="utf-8")
    result = state(course)
    assert all(skill["grade"] is None for skill in result["skills"])
    assert any(exam in warning and "git" in warning for warning in result["vault_warnings"])
    with pytest.raises(ToolError, match="isn't valid JSON"):
        read_exam(exam)


def test_a_broken_home_is_left_as_it_is(course, vault):
    home = vault / "Home.md"
    start("terminal", "alice", course)
    home.write_text("---\ntype: [home\n---\n\nMy own home", encoding="utf-8")
    result = start("terminal", "alice", course)
    assert home.read_text(encoding="utf-8").endswith("My own home")
    assert any("Home.md" in warning for warning in result["vault_warnings"])


def test_no_warning_on_a_healthy_vault(course, vault):
    assert "vault_warnings" not in start("terminal", "alice", course)
