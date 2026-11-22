import pytest

from teach_me.database import blocks, objects
from teach_me.database import plan as plans
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import create_course, create_exam, create_skills, edit_course, get_course_state, list_courses, save_class, start_session
from tests.conftest import ONE_STEP, PLAN

QUESTION = {"kind": "single", "text": "?", "skills": ["convolution"], "options": ["Yes", "No"], "correct_options": ["A"]}


def note(vault, stem):
    folder = "classes" if stem.startswith("class-") else "exams"
    return vault_io.read(vault / "courses" / "computer-vision" / folder / f"{stem}.md")


def test_each_step_is_a_planned_note(course, vault):
    stems = ["class-convolution", "quiz-convolution-quiz", "class-cnn-architectures", "exercise-first-cnn"]
    for order, stem in enumerate(stems, 1):
        metadata = note(vault, stem).metadata
        assert metadata["order"] == order and metadata["status"] == "planned" and metadata["course"] == "[[course-computer-vision]]"
    last = note(vault, "exercise-first-cnn")
    assert last.metadata["type"] == "exercise" and last.metadata["description"] == "Train a CNN on the pictures"
    assert last.metadata["skills"] == ["[[skill-convolution]]", "[[skill-cnn-architecture]]"] and last.metadata["importance"] == "core"
    assert "> [!todo] Planned" in last.body
    assert "![[course.base#Next steps]]" in objects.get_course(course).body
    state = get_course_state(course)
    assert state["plan"]["done"] == 0 and state["plan"]["total"] == 4
    assert [step["slug"] for step in state["plan"]["next_steps"]] == ["convolution", "convolution-quiz", "cnn-architectures"]
    assert state["pending_exams"] == []  # a planned exam isn't waiting for answers


def test_create_course_checks_the_plan(course):
    with pytest.raises(ToolError, match="Give the plan"):
        create_course("alice", "Subject", "", ["convolution"], plan=[], name="Other")
    with pytest.raises(ToolError, match="doesn't have the skills pooling"):
        create_course("alice", "Subject", "", ["convolution"], plan=[{**PLAN[0], "skills": ["pooling"]}], name="Other")
    with pytest.raises(ToolError, match="unknown kind 'lecture'"):
        create_course("alice", "Subject", "", ["convolution"], plan=[{**PLAN[0], "kind": "lecture"}], name="Other")
    classes = [{**PLAN[0], "title": f"Class {number}"} for number in range(4)]
    created = create_course("alice", "Subject", "", ["convolution", "cnn-architecture"], plan=[*classes, PLAN[1]], name="Other")
    assert created["warnings"] == [
        "No exam of the plan evaluates the skills cnn-architecture : add exams for them, or add them to the skills of planned exams.",
        "4 classes in a row without an exam (class-0 → class-3) : plan an exercise at least every 3 classes.",
    ]
    assert created["plan"][4]["slug"] == "convolution-quiz-2"  # the slugs planned by the other courses are taken


def test_a_course_that_already_exists_is_refused(course):
    with pytest.raises(ToolError, match="already has the course 'computer-vision'.*edit_course"):
        create_course("alice", "Again", "", ["convolution"], plan=ONE_STEP, name="Computer Vision")


def test_a_document_outside_the_plan_is_added_with_a_warning(course, vault):
    save_class(course, "Convolution", "", "Content", planned="convolution")
    saved = save_class(course, "Padding", "Borders of the picture", "Content")
    assert saved["slug"] == "padding" and "wasn't in the plan" in saved["warnings"][0]
    assert "convolution-quiz" not in saved["warnings"][0] and "cnn-architectures ('CNN architectures')" in saved["warnings"][0]
    steps = plans.course_plan(objects.get_course(course))
    assert [step["slug"] for step in steps][:3] == ["convolution", "padding", "convolution-quiz"]  # after the last step done
    padding = note(vault, "class-padding").metadata
    assert padding["added"] is True and padding["order"] == 2 and padding["status"] == "done"
    assert note(vault, "quiz-convolution-quiz").metadata["order"] == 3
    exam = create_exam(course, "Surprise", "quiz", [QUESTION])
    assert "wasn't in the plan" in exam["warnings"][0]
    assert plans.course_plan(objects.get_course(course))[2]["skills"] == ["convolution"]


def test_planned_class_must_be_a_class_to_do(course):
    with pytest.raises(ToolError, match="is a quiz, not a class"):
        save_class(course, "Quiz", "", "Content", planned="convolution-quiz")
    save_class(course, "Convolution", "", "Content", planned="convolution")
    with pytest.raises(ToolError, match="already has its document"):
        save_class(course, "Convolution", "", "Content", planned="convolution")


def test_what_the_student_wrote_in_a_planned_note_is_kept(course, vault):
    path = vault / "courses/computer-vision/classes/class-convolution.md"
    path.write_text(path.read_text(encoding="utf-8").replace("## ✏️ My notes", "## ✏️ My notes\n\nWhat is a kernel ?"), encoding="utf-8")
    save_class(course, "Convolution", "", "# Convolution\n\nContent", planned="convolution")
    body = vault_io.read(path).body
    assert body.startswith("# Convolution") and "Planned" not in body
    assert blocks.notes(body) == "What is a kernel ?"


def test_edit_course_changes_the_plan_step_by_step(course, vault):
    create_skills("alice", [{"name": "Pooling", "description": "Downsamples a feature map"}])
    edited = edit_course(
        course,
        add_skills=["pooling"],
        add_steps=[{"kind": "class", "title": "Pooling", "description": "Max and average", "skills": ["pooling"], "importance": "optional"}],
        insert_after="convolution",
        update_steps=[{"step": "first-cnn", "skills": ["convolution", "cnn-architecture", "pooling"], "title": "My first CNN"}, {"step": "cnn-architectures", "move_after": ""}],
        remove_steps=["convolution-quiz"],
    )
    assert [step["slug"] for step in edited["plan"]] == ["cnn-architectures", "convolution", "pooling", "first-cnn"]
    assert edited["plan"][3]["title"] == "My first CNN" and edited["plan"][3]["progress"] == "planned"
    assert edited["skills"] == ["convolution", "cnn-architecture", "pooling"]
    assert edited["warnings"] == [] and edited["replaced"] == {}
    assert note(vault, "exercise-first-cnn").metadata["title"] == "My first CNN"
    assert [note(vault, stem).metadata["order"] for stem in ("class-cnn-architectures", "class-convolution", "class-pooling", "exercise-first-cnn")] == [1, 2, 3, 4]
    assert not (vault / "courses/computer-vision/exams/quiz-convolution-quiz.md").exists()  # nothing was written in it


def test_a_removed_step_the_student_wrote_in_is_dropped(course, vault):
    path = vault / "courses/computer-vision/exams/quiz-convolution-quiz.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n\nRevise the kernels first\n", encoding="utf-8")
    edit_course(course, remove_steps=["convolution-quiz"])
    assert vault_io.read(path).metadata["status"] == "dropped"
    assert "convolution-quiz" not in [step["slug"] for step in get_course_state(course)["plan"]["next_steps"]]


def test_the_skills_of_an_exam_given_are_its_questions(course):
    create_exam(course, "Convolution quiz", "quiz", [QUESTION], planned="convolution-quiz")
    with pytest.raises(ToolError, match="already given"):
        edit_course(course, update_steps=[{"step": "convolution-quiz", "skills": ["cnn-architecture"]}])


def test_edit_course_texts_and_status(course):
    edited = edit_course(course, add_to_starting_level="Already used OpenCV.", subject="Computer vision for my pets.")
    assert edited["starting_level"] == "Knows linear algebra and basic neural networks.\n\nAlready used OpenCV."
    assert edited["replaced"] == {"subject": "Computer vision with convolutional neural networks."}
    assert edit_course(course, status="abandoned")["status"] == "abandoned"
    assert list_courses("alice")[0]["status"] == "abandoned"
    assert "abandoned : ask the student whether they want to resume it" in start_session("app", user="alice", course=course)["next_step"]
    with pytest.raises(ToolError, match="Unknown status"):
        edit_course(course, status="paused")
    with pytest.raises(ToolError, match="Nothing to update"):
        edit_course(course)


def test_edit_course_keeps_what_is_used(course):
    save_class(course, "Convolution", "", "Content", planned="convolution")
    with pytest.raises(ToolError, match="already has its document : it can't be removed"):
        edit_course(course, remove_steps=["convolution"])
    with pytest.raises(ToolError, match=r"still used : convolution \(step convolution, step convolution-quiz, step first-cnn\)"):
        edit_course(course, remove_skills=["convolution"])
    with pytest.raises(ToolError, match="doesn't have the skills pooling"):
        edit_course(course, update_steps=[{"step": "convolution-quiz", "skills": ["pooling"]}])
    with pytest.raises(ToolError, match="give `add_steps` too"):
        edit_course(course, insert_after="convolution")
    assert edit_course(course, remove_projects=["pet-classifier"])["projects"] == []


def test_start_session_points_to_the_next_step(course):
    assert 'planned="convolution"' in start_session("terminal", user="alice", course=course)["next_step"]


def test_the_views_of_a_course_are_written_again_when_broken(course, vault):
    document = objects.get_course(course)
    document.body = document.body.replace("![[course.base#Plan]]", "My own plan")
    vault_io.write(document)
    start_session("app", user="alice", course=course)
    body = objects.get_course(course).body
    assert "![[course.base#Plan]]" in body and "> My own plan" in blocks.notes(body)
