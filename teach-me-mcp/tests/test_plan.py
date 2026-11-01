import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import create_course, create_exam, create_skills, edit_course, get_course_state, list_courses, save_class, start_session
from tests.conftest import ONE_STEP, PLAN

QUESTION = {"kind": "single", "text": "?", "skills": ["convolution"], "options": ["Yes", "No"], "correct_options": ["A"]}


def test_the_plan_is_a_table_of_links(course):
    document = objects.get_course(course)
    assert [step["slug"] for step in document.metadata["plan"]] == ["convolution", "convolution-quiz", "cnn-architectures", "first-cnn"]
    assert "| # | Step | Type | Description | Skills | Importance | Progress |" in document.body
    assert "| 4 | [[exercise-first-cnn\\|First CNN]] | 🛠️ project | Train a CNN on the pictures | convolution, cnn-architecture | core | ⏳ planned |" in document.body
    state = get_course_state(course)
    assert state["plan"]["done"] == 0 and state["plan"]["total"] == 4
    assert [step["slug"] for step in state["plan"]["next_steps"]] == ["convolution", "convolution-quiz", "cnn-architectures"]


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


def test_a_document_outside_the_plan_is_added_with_a_warning(course):
    save_class(course, "Convolution", "", "Content", planned="convolution")
    saved = save_class(course, "Padding", "Borders of the picture", "Content")
    assert saved["slug"] == "padding" and "wasn't in the plan" in saved["warnings"][0]
    assert "convolution-quiz" not in saved["warnings"][0] and "cnn-architectures ('CNN architectures')" in saved["warnings"][0]
    steps = objects.get_course(course).metadata["plan"]
    assert [step["slug"] for step in steps][:3] == ["convolution", "padding", "convolution-quiz"]  # after the last step done
    assert steps[1]["added"] is True and "optional · ➕ added" in objects.get_course(course).body
    exam = create_exam(course, "Surprise", "quiz", [QUESTION])
    assert "wasn't in the plan" in exam["warnings"][0]
    assert objects.get_course(course).metadata["plan"][2]["skills"] == ["convolution"]


def test_planned_class_must_be_a_class_to_do(course):
    with pytest.raises(ToolError, match="is a quiz, not a class"):
        save_class(course, "Quiz", "", "Content", planned="convolution-quiz")
    save_class(course, "Convolution", "", "Content", planned="convolution")
    with pytest.raises(ToolError, match="already has its document"):
        save_class(course, "Convolution", "", "Content", planned="convolution")


def test_edit_course_changes_the_plan_step_by_step(course):
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
    assert "[[exercise-first-cnn\\|My first CNN]]" in objects.get_course(course).body


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


def test_a_course_created_before_the_plans_gets_one(course, vault):
    save_class(course, "Convolution", "Kernels", "Content", planned="convolution")
    document = objects.get_course(course)
    del document.metadata["plan"]
    del document.metadata["status"]
    start = document.body.index("## Plan")
    end = document.body.index("## 20")
    document.body = document.body[:start] + "## Content\n\n1. Class : [[class-convolution|Convolution]]\n\n" + document.body[end:]
    vault_io.write(document)

    state = get_course_state(course)
    assert state["status"] == "active" and state["plan"]["done"] == 1 and state["plan"]["total"] == 1
    start_session("app", user="alice", course=course)  # migrates it
    migrated = objects.get_course(course)
    assert migrated.metadata["plan"] == [{"slug": "convolution", "kind": "class", "title": "Convolution", "description": "Kernels", "skills": [], "importance": "core"}]
    assert "## Content" not in migrated.body and migrated.body.startswith("## Plan")
