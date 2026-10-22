from datetime import timedelta

import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import (
    create_course,
    create_project,
    create_user,
    get_course_state,
    list_courses,
    list_users,
    log_session,
    save_class,
)


def test_create_course(course, vault):
    assert course == "computer-vision"
    document = objects.get_course(course)
    assert document.metadata["user"] == "[[alice]]"
    assert document.metadata["projects"] == ["[[pet-classifier]]"]
    assert [skill["name"] for skill in document.metadata["skills"]] == ["convolution", "cnn-architecture"]
    assert len(objects.parse_sessions(document.body)) == 1


def test_course_slug_defaults_to_the_subject(vault):
    create_user("Alice")
    slug = create_course("alice", "Machine learning for time series forecasting.", "", [{"name": "arima", "description": ""}])
    assert slug == "machine-learning-for-time-series"


def test_course_needs_skills(vault):
    create_user("Alice")
    with pytest.raises(ToolError, match="ALL the skills"):
        create_course("alice", "Subject", "Level", skills=[])


def test_course_project_must_exist_and_belong_to_the_user(vault):
    create_user("Alice")
    create_user("Bob")
    create_project("bob", "Robot", "A robot")
    skills = [{"name": "a", "description": ""}]
    with pytest.raises(ToolError, match="Unknown project"):
        create_course("alice", "Subject", "Level", skills, projects=["nope"])
    with pytest.raises(ToolError, match="belongs to 'bob'"):
        create_course("alice", "Subject", "Level", skills, projects=["robot"])


def test_list_courses_and_users_activity(course):
    create_course("alice", "Second course", "", [{"name": "a", "description": ""}], name="Second")
    assert {c["slug"] for c in list_courses("alice")} == {"computer-vision", "second"}
    assert list_users()[0]["last_activity"] is not None


def test_log_session_appends_to_the_current_session(course):
    label = log_session(course, "Prefers visual explanations")
    assert log_session(course, "Struggled with the integral limits") == label
    sessions = get_course_state(course)["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["entries"].endswith("- Prefers visual explanations\n- Struggled with the integral limits")


def test_new_session_after_inactivity(course):
    log_session(course, "First session")
    document = objects.get_course(course)
    document.metadata["updated_at"] = vault_io.format_time(vault_io.now() - objects.SESSION_TIMEOUT - timedelta(minutes=1))
    vault_io.write(document)
    log_session(course, "Second session")
    sessions = get_course_state(course)["sessions"]
    assert len(sessions) == 2
    assert sessions[0]["entries"] == "- Second session"  # most recent first


def test_save_class(course, vault):
    path = save_class(course, "Convolution", "Definition and kernels", "# Convolution\n\nContent")
    assert path.startswith("courses/computer-vision/classes/") and path.endswith("-convolution.md")
    document = vault_io.read(vault / path)
    assert document.metadata["title"] == "Convolution"
    assert document.body == "# Convolution\n\nContent"
    assert "Class [[" in get_course_state(course)["sessions"][0]["entries"]


def test_same_class_title_gets_a_new_slug(course):
    first = save_class(course, "Convolution", "", "Content")
    second = save_class(course, "Convolution", "", "Content")
    assert first != second and second.endswith("-convolution-2.md")
