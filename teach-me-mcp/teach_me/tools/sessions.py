"""Session log and classes."""

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError


def log_session(course: str, entry: str) -> str:
    """Appends an entry to the current session of a course. A new session is started when the last activity on the course is older than 3 hours.

    Classes, exams and shared resources are logged automatically : use this tool for the observations.

    Args:
        course (str): The slug of the course
        entry (str): 1-3 lines : what was done, and the observations that matter for the next sessions

    Returns:
        str: The session the entry was added to (YYYY-MM-DD HH:MM)
    """
    if not (entry or "").strip():
        raise ToolError("The `entry` is empty.")
    document = objects.get_course(course)
    label = objects.append_to_session(document, entry)
    vault.write(document)
    return label


def save_class(course: str, title: str, summary: str, content: str) -> str:
    """Saves the content of a class that has just been taught.

    Args:
        course (str): The slug of the course
        title (str): The title of the class
        summary (str): 2-4 sentences about what has been taught
        content (str): The class itself, in markdown

    Returns:
        str: The path of the class file, relative to the vault
    """
    if not (title or "").strip():
        raise ToolError("The class needs a non empty `title`.")
    if not (content or "").strip():
        raise ToolError("The class `content` is empty : send the class itself, in markdown.")
    course_document = objects.get_course(course)
    path = objects.new_document_path(course, "classes", title)
    label = objects.current_session(course_document)
    vault.write(
        Document(
            path,
            {
                "title": title.strip(),
                "summary": (summary or "").strip(),
                "session": label,
                "created_at": vault.format_time(vault.now()),
            },
            content,
        )
    )
    objects.append_to_session(course_document, f"Class {vault.link(path.stem)} : {title.strip()}")
    vault.write(course_document)
    return vault.relative(path)
