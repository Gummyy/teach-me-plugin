from datetime import timedelta

import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import (
    create_course,
    create_project,
    create_skills,
    create_user,
    get_course_state,
    list_courses,
    list_projects,
    list_users,
    log_session,
    save_class,
    start_session,
    update_project,
)


def test_create_course(course, vault):
    assert course == "computer-vision"
    document = objects.get_course(course)
    assert document.metadata["user"] == "[[alice]]"
    assert document.metadata["projects"] == ["[[pet-classifier]]"]
    assert document.metadata["skills"] == ["[[convolution]]", "[[cnn-architecture]]"]
    assert len(objects.parse_sessions(document.body)) == 1


def test_course_slug_defaults_to_the_subject(vault):
    create_user("Alice")
    create_skills("alice", [{"name": "arima", "description": ""}])
    slug = create_course("alice", "Machine learning for time series forecasting.", "", ["arima"])
    assert slug == "machine-learning-for-time-series"


def test_course_needs_skills(vault):
    create_user("Alice")
    with pytest.raises(ToolError, match="ALL the skills"):
        create_course("alice", "Subject", "Level", skills=[])


def test_course_skills_must_exist_and_belong_to_the_user(vault):
    create_user("Alice")
    create_user("Bob")
    create_skills("bob", [{"name": "Welding", "description": ""}])
    with pytest.raises(ToolError, match="Unknown skill 'nope'.*create_skills"):
        create_course("alice", "Subject", "Level", ["nope"])
    with pytest.raises(ToolError, match="belongs to 'bob'"):
        create_course("alice", "Subject", "Level", ["welding"])


def test_course_project_must_exist_and_belong_to_the_user(vault):
    create_user("Alice")
    create_user("Bob")
    create_project("bob", "Robot", "A robot")
    create_skills("alice", [{"name": "a", "description": ""}])
    skills = ["a"]
    with pytest.raises(ToolError, match="Unknown project"):
        create_course("alice", "Subject", "Level", skills, projects=["nope"])
    with pytest.raises(ToolError, match="belongs to 'bob'"):
        create_course("alice", "Subject", "Level", skills, projects=["robot"])


def test_list_courses_and_users_activity(course):
    create_course("alice", "Second course", "", ["convolution"], name="Second")  # skills are shared by the courses of a user
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


def test_update_project_keeps_its_history(course):
    update_project("pet-classifier", progress="Dataset collected : 2000 pictures")
    project = update_project("pet-classifier", progress="First CNN trained", description="Classify cats, dogs and rabbits.")
    assert project["description"] == "Classify cats, dogs and rabbits."
    assert [entry.split(" : ", 1)[1] for entry in project["last_progress"]] == ["Dataset collected : 2000 pictures", "First CNN trained"]
    assert get_course_state(course)["projects"][0]["name"] == "Pet classifier"
    with pytest.raises(ToolError, match="Nothing to update"):
        update_project("pet-classifier")


def test_start_session(course):
    create_user("Bob")
    several = start_session("terminal")
    assert {u["slug"] for u in several["users"]} == {"alice", "bob"} and "who they are" in several["next_step"]

    without_course = start_session("app", user="alice")
    assert [c["slug"] for c in without_course["courses"]] == ["computer-vision"]
    assert without_course["course"] is None and "start_session again with `course`" in without_course["next_step"]

    session = start_session("terminal", user="alice", course=course)
    assert session["course"]["slug"] == course
    assert "Session in the terminal" in session["course"]["sessions"][0]["entries"]
    with pytest.raises(ToolError, match="belongs to 'alice'"):
        start_session("terminal", user="bob", course=course)
    with pytest.raises(ToolError, match="Unknown interface"):
        start_session("phone")


def test_start_session_merges_the_preferences_of_the_interface(vault):
    create_user("Alice", preferences={"tone": "casual", "quizzes": "anywhere"}, interface_preferences={"terminal": {"quizzes": "in the vault"}})
    assert start_session("terminal")["preferences"] == {"tone": "casual", "quizzes": "in the vault"}
    assert start_session("app")["preferences"] == {"tone": "casual", "quizzes": "anywhere"}
    assert "no course yet" in start_session("app")["next_step"]
    vault_empty = vault / "users" / "alice.md"
    assert vault_empty.is_file()


def test_list_projects(course):
    create_user("Bob")
    create_project("bob", "Robot", "A robot")
    create_project("alice", "Photo album", "Sort my pictures.")
    update_project("pet-classifier", progress="Dataset collected")
    projects = list_projects("alice")
    assert {project["slug"] for project in projects} == {"pet-classifier", "photo-album"}
    pet = next(project for project in projects if project["slug"] == "pet-classifier")
    assert pet["description"] == "Classify the pictures of my cats and dogs."
    assert pet["last_progress"][0].endswith("Dataset collected")
    assert list_projects("bob")[0]["name"] == "Robot"
