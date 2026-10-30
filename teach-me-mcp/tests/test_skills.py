import pytest

from teach_me.database import objects
from teach_me.errors import ToolError
from teach_me.tools import correct_exam, create_course, create_exam, create_skills, create_user, edit_skill, grade_questions, list_skills, report_card, submit_answers

QUESTION = {"kind": "single", "text": "?", "skills": ["convolution"], "options": ["Yes", "No"], "correct_options": ["A"]}


def test_create_skills(course):
    document = objects.get_skill("convolution")
    assert document.metadata["name"] == "convolution" and document.metadata["user"] == "[[user-alice]]"
    assert document.body == "Computes and interprets a 2D convolution"
    created = create_skills("alice", [{"name": "Pooling", "description": "Downsamples a feature map"}, {"name": "CONVOLUTION", "description": "Other"}])
    assert created == [{"slug": "pooling", "name": "Pooling", "reused": False}, {"slug": "convolution", "name": "convolution", "reused": True}]
    assert objects.get_skill("convolution").body == "Computes and interprets a 2D convolution"  # a reused skill keeps its description


def test_create_skills_checks_its_arguments(vault):
    create_user("Alice")
    create_user("Bob")
    with pytest.raises(ToolError, match="at least one skill"):
        create_skills("alice", [])
    with pytest.raises(ToolError, match="appears twice"):
        create_skills("alice", [{"name": "a", "description": ""}, {"name": "A", "description": ""}])
    create_skills("alice", [{"name": "Sorting", "description": ""}])
    assert create_skills("bob", [{"name": "Sorting", "description": ""}]) == [{"slug": "sorting-2", "name": "Sorting", "reused": False}]  # skills aren't shared between users


def test_list_skills(course):
    create_skills("alice", [{"name": "Pooling", "description": ""}])
    assert [skill["slug"] for skill in list_skills("alice")] == ["cnn-architecture", "convolution", "pooling"]
    assert [skill["slug"] for skill in list_skills("alice", course)] == ["convolution", "cnn-architecture"]  # in the order of the course
    create_user("Bob")
    with pytest.raises(ToolError, match="belongs to 'alice'"):
        list_skills("bob", course)


def test_edit_skill(course):
    edited = edit_skill("convolution", name="2D convolution", description="Computes a 2D convolution by hand")
    assert edited == {"slug": "convolution", "name": "2D convolution", "description": "Computes a 2D convolution by hand", "grade": None, "score": None}
    with pytest.raises(ToolError, match="already has a skill named"):
        edit_skill("convolution", name="CNN-architecture")
    with pytest.raises(ToolError, match="Nothing to update"):
        edit_skill("convolution")


def test_a_skill_shared_by_two_courses_has_one_history(course):
    second = create_course("alice", "Image processing", "", ["convolution"], name="Image processing")
    first_exam = create_exam(course, "First", "quiz", [QUESTION])["slug"]
    second_exam = create_exam(second, "Second", "quiz", [QUESTION])["slug"]
    for exam, answer in ((first_exam, "B"), (second_exam, "A")):
        submit_answers(exam, [answer])
        grade_questions(exam, [{"question": 1, "explanation": "."}])
        correct_exam(exam)
    assert objects.skill_grades("alice") == {"convolution": {"grade": "B", "score": 3.0, "history": ["D", "A"]}}
    assert list_skills("alice", course)[0]["grade"] == "B"
    assert "| B (3.0/5) | D → A |" in report_card(course)
