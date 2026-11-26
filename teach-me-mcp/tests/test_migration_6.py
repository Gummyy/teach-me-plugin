"""Migration 6, on a vault at version 5 : the project exams given become quizzes, the planned ones deliverables."""

import json

from teach_me.database import dashboards, migrations, objects
from teach_me.database import plan as plans
from teach_me.database import vault as vault_io
from teach_me.tools import get_course_state, migrate_vault, read_exam
from tests.test_exams import GRADES, _correct, _create, _grades


def _legacy(vault, course):
    """The vault as version 5 left it : the quiz of the plan was given as a project exam, and a project exam is still planned."""
    exam = _create(course, planned="convolution-quiz")
    _correct(exam["slug"], ["A", "A, B", "x"], GRADES)
    quiz_path = vault / exam["path"]
    old = quiz_path.with_name("exercise-convolution-quiz.md")
    text = quiz_path.read_text(encoding="utf-8").replace("id: quiz-convolution-quiz", "id: exercise-convolution-quiz").replace("type: quiz", "type: exercise")
    old.write_text(text, encoding="utf-8")
    quiz_path.unlink()
    data_file = objects.exam_data_file("convolution-quiz")
    data_file.write_text(json.dumps({**json.loads(data_file.read_text(encoding="utf-8")), "type": "project"}), encoding="utf-8")
    course_file = objects.course_file(course)
    course_file.write_text(course_file.read_text(encoding="utf-8").replace("[[quiz-convolution-quiz", "[[exercise-convolution-quiz"), encoding="utf-8")
    steps = plans.course_plan(objects.get_course(course))
    plans.write_plan(course, [*steps, {"slug": "pet-detector", "kind": "project", "title": "Pet detector", "description": "", "skills": ["convolution"], "importance": "core"}])
    (vault / "bases" / "home.base").write_text("# the base of version 5", encoding="utf-8")
    (vault / ".teach-me" / "version").write_text("5\n")


def test_migration_6_turns_the_project_exams_into_quizzes_and_deliverables(course, vault):
    _legacy(vault, course)
    assert objects.EXAM_COEFFICIENTS[objects.exam_type(vault_io.read(vault / "courses/computer-vision/exams/exercise-convolution-quiz.md"))] == 2
    result = migrate_vault()
    assert result["from"] == 5 and result["to"] == migrations.current_version()
    exams = vault / "courses" / "computer-vision" / "exams"
    assert not list(exams.glob("exercise-*.md"))

    given = vault_io.read(exams / "quiz-convolution-quiz.md")
    assert given.metadata["id"] == "quiz-convolution-quiz" and given.metadata["type"] == "quiz" and given.metadata["status"] == "corrected"
    assert objects.exam_data("convolution-quiz")["type"] == "quiz"
    assert read_exam("convolution-quiz")["answers"][0] == ["A"]  # the questions and the answers are unchanged
    assert "[[quiz-convolution-quiz" in objects.get_course(course).body and "exercise-convolution-quiz" not in objects.get_course(course).body
    assert _grades("alice")["convolution"]["history"] == ["A"]

    planned = vault_io.read(exams / "deliverable-pet-detector.md")
    assert planned.metadata["id"] == "deliverable-pet-detector" and planned.metadata["type"] == "deliverable" and planned.metadata["status"] == "planned"
    assert planned.body.strip() == plans.placeholder("deliverable").strip() and "This deliverable comes later" in planned.body
    steps = {step["slug"]: step["kind"] for step in plans.course_plan(objects.get_course(course))}
    assert steps["pet-detector"] == "deliverable" and steps["convolution-quiz"] == "quiz" and get_course_state(course)["plan"]["done"] == 1

    assert (vault / "bases" / "home.base").read_text(encoding="utf-8") == dashboards.HOME_BASE
    assert "![[project.base#Deliverables]]" in objects.get_project("pet-classifier").body
    assert any(change.startswith("courses/computer-vision/exams/exercise-convolution-quiz.md → ") for change in result["changes"])
    migrations.check_current()


def test_a_planned_project_exam_the_student_wrote_in_keeps_its_notes(course, vault):
    _legacy(vault, course)
    path = vault / "courses/computer-vision/exams/exercise-pet-detector.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nUse the webcam.\n", encoding="utf-8")
    migrate_vault()
    body = vault_io.read(vault / "courses/computer-vision/exams/deliverable-pet-detector.md").body
    assert "Use the webcam." in body
