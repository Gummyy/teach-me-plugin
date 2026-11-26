"""A class is `new` when save_class writes it, and `read` once the student went through it : the model calls update_class,
or the student changes the status in Obsidian. Only a class read counts as done in the plan."""

import re

import pytest

from teach_me.database import migrations, objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import get_course_state, migrate_vault, save_class, start_session, update_class


def _lesson(vault, course, slug="convolution"):
    return vault / "courses" / course / "classes" / f"class-{slug}.md"


def test_a_class_is_new_until_it_is_read(course, vault):
    save_class(course, "Convolution", "", "Content", planned="convolution")
    result = start_session("terminal", "alice", course)
    assert [lesson["slug"] for lesson in result["course"]["classes_to_read"]] == ["convolution"]
    assert "hasn't marked as read the classes 'Convolution'" in result["next_step"]
    assert "pass planned=\"convolution-quiz\"" in result["next_step"]  # the next step not started yet
    update_class(course, "convolution", "read")
    assert vault_io.read(_lesson(vault, course)).metadata["status"] == "read"
    assert "marked as read" not in start_session("terminal", "alice", course)["next_step"]
    update_class(course, "convolution", "new")  # to read again
    assert get_course_state(course)["plan"]["done"] == 0


@pytest.mark.parametrize("typed", ["read", "Read", "done"])
def test_the_student_marks_a_class_read_in_obsidian(course, vault, typed):
    save_class(course, "Convolution", "", "Content", planned="convolution")
    path = _lesson(vault, course)
    path.write_text(re.sub(r"^status: new$", f"status: {typed}", path.read_text(encoding="utf-8"), flags=re.MULTILINE), encoding="utf-8")
    state = get_course_state(course)
    assert state["classes_to_read"] == [] and state["plan"]["done"] == 1


def test_update_class_refuses_a_class_without_content(course):
    with pytest.raises(ToolError, match="planned : it has no content yet"):
        update_class(course, "convolution", "read")
    with pytest.raises(ToolError, match="Unknown class 'nope'"):
        update_class(course, "nope", "read")
    with pytest.raises(ToolError, match="Unknown status"):
        update_class(course, "convolution", "done")


def test_migration_5_marks_the_classes_given_as_read(course, vault):
    save_class(course, "Convolution", "", "Content", planned="convolution")
    path = _lesson(vault, course)
    path.write_text(path.read_text(encoding="utf-8").replace("status: new", "status: done"), encoding="utf-8")
    (vault / ".teach-me").mkdir(exist_ok=True)
    (vault / ".teach-me" / "version").write_text("4\n")
    result = migrate_vault()
    assert result["to"] == migrations.current_version()
    assert vault_io.read(path).metadata["status"] == "read"
    assert "Classes to read" in (vault / "bases" / "home.base").read_text(encoding="utf-8")
    assert "![[home.base#Classes to read]]" in (vault / "Home.md").read_text(encoding="utf-8")
    assert "until you read it" in objects.get_course(course).body
