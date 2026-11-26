"""Migration 5 : a class is `new` until the student read it, then `read`.

Every class saved before was presented in the chat : its status `done` becomes `read`. The bases are written again
(the progress of a class, the classes to read in the next steps and in Home.md), and so are the views of Home.md and of the course notes.
"""

from __future__ import annotations

from teach_me.database import dashboards, migration_2, objects, vault


def class_statuses() -> list[str]:
    changed = []
    for document in vault.read_all(sorted(objects.courses_dir().glob(f"*/classes/{objects.PREFIXES['class']}*.md"))):
        if document.metadata.get("type") == "class" and document.metadata.get("status") == "done":
            document.metadata["status"] = "read"
            vault.write(document)
            changed.append(f"{vault.relative(document.path)} : status read")
    return changed


def course_views() -> list[str]:
    changed = []
    for course in objects.iter_courses():
        before = course.body
        dashboards.render_course(course)
        if course.body != before:
            vault.write(course)
            changed.append(f"{vault.relative(course.path)} : views")
    return changed


def run() -> list[str]:
    return class_statuses() + migration_2.views() + course_views()  # the views of version 2, written again with the bases of this version
