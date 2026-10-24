"""The objects of the data model, and where they live in the vault.

    users/<user>.md
    projects/<project>.md
    courses/<course>/course.md        (skills, resources and the session log)
    courses/<course>/classes/<class>.md
    courses/<course>/exams/<exam>.md   (evaluations in the frontmatter)
    courses/<course>/report_card.md   (generated)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

from teach_me.database import vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

SESSION_TIMEOUT = timedelta(hours=3)
"""A new session starts when the last activity on a course is older than this."""
SESSION_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})[ \t]*$", re.MULTILINE)
EXAM_TYPES = ("quiz", "project")
EXAM_STATUSES = ("assigned", "filled", "corrected")
RESOURCE_STATUSES = ("new", "explained", "dropped")
DOCUMENT_KINDS = ("classes", "exams")


# --------------------------------------------------------------------------- #
# Folders
# --------------------------------------------------------------------------- #


def users_dir() -> Path:
    return vault.vault_path() / "users"


def projects_dir() -> Path:
    return vault.vault_path() / "projects"


def courses_dir() -> Path:
    return vault.vault_path() / "courses"


def course_file(course: str) -> Path:
    return courses_dir() / course / "course.md"


def _known(paths: Iterator[Path], limit: int = 20) -> str:
    names = sorted(path.stem if path.suffix == ".md" else path.name for path in paths)
    if not names:
        return "none"
    return ", ".join(names[:limit]) + (", ..." if len(names) > limit else "")


# --------------------------------------------------------------------------- #
# Users and projects
# --------------------------------------------------------------------------- #


def get_user(user: str) -> Document:
    path = users_dir() / f"{user}.md"
    if not path.is_file():
        raise ToolError(
            f"Unknown user '{user}'. Known users : {_known(users_dir().glob('*.md'))}. "
            "Use the slug returned by list_users or create_user."
        )
    return vault.read(path)


def iter_users() -> Iterator[Document]:
    for path in sorted(users_dir().glob("*.md")):
        yield vault.read(path)


def get_project(project: str) -> Document:
    path = projects_dir() / f"{project}.md"
    if not path.is_file():
        raise ToolError(
            f"Unknown project '{project}'. Known projects : {_known(projects_dir().glob('*.md'))}. "
            "Create it first with create_project."
        )
    return vault.read(path)


# --------------------------------------------------------------------------- #
# Courses
# --------------------------------------------------------------------------- #


def get_course(course: str) -> Document:
    path = course_file(course)
    if not path.is_file():
        courses = (p.parent for p in courses_dir().glob("*/course.md"))
        raise ToolError(
            f"Unknown course '{course}'. Known courses : {_known(courses)}. "
            "Use the slug returned by list_courses or create_course."
        )
    return vault.read(path)


def course_slug(document: Document) -> str:
    """The slug of a course is the name of its folder (the file is always course.md)."""
    return document.path.parent.name


def iter_courses(user: Optional[str] = None) -> Iterator[Document]:
    for path in sorted(courses_dir().glob("*/course.md")):
        document = vault.read(path)
        if user is None or vault.unlink(document.metadata.get("user", "")) == user:
            yield document


def last_activity(document: Document) -> Optional[datetime]:
    metadata = document.metadata
    return vault.parse_time(metadata.get("updated_at")) or vault.parse_time(metadata.get("created_at"))


def declared_skills(course: Document) -> list[str]:
    return [str(skill.get("name")) for skill in course.metadata.get("skills") or [] if isinstance(skill, dict)]


# --------------------------------------------------------------------------- #
# Sessions : dated entries in the body of course.md
# --------------------------------------------------------------------------- #


def parse_sessions(body: str) -> list[tuple[str, str]]:
    """Returns the sessions of a course log as (label, entries), in chronological order."""
    matches = list(SESSION_HEADING.finditer(body))
    sessions = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sessions.append((match.group(1), body[match.end():end].strip("\n")))
    return sessions


def current_session(course: Document) -> str:
    """Returns the label of the current session of a course, starting a new one if needed.

    Also records the activity (updated_at). The caller must write the document.
    """
    moment = vault.now()
    sessions = parse_sessions(course.body)
    previous = last_activity(course)
    if not sessions or previous is None or moment - previous > SESSION_TIMEOUT:
        label = vault.format_session(moment)
        course.body = f"{course.body.rstrip()}\n\n## {label}\n".lstrip("\n")
    else:
        label = sessions[-1][0]
    course.metadata["updated_at"] = vault.format_time(moment)
    return label


def append_to_session(course: Document, entry: str) -> str:
    """Appends an entry to the current session of a course and returns the session label.

    The current session is always the last one, so the entry goes at the end of the body.
    The caller must write the document.
    """
    label = current_session(course)
    lines = [line.rstrip() for line in entry.strip().splitlines() if line.strip()]
    if not lines:
        return label
    first, *rest = lines
    bullet = first if first.lstrip().startswith(("- ", "* ")) else f"- {first}"
    text = "\n".join([bullet, *(f"  {line.strip()}" for line in rest)])
    separator = "\n\n" if course.body.rstrip().endswith(f"## {label}") else "\n"
    course.body = f"{course.body.rstrip()}{separator}{text}\n"
    return label


# --------------------------------------------------------------------------- #
# Classes and exams
# --------------------------------------------------------------------------- #


def new_document_path(course: str, kind: str, title: str) -> Path:
    """Path of a new class / exam : courses/<course>/<kind>/<YYYY-MM-DD>-<title>.md

    Slugs are unique in the whole vault, so that tools can find a document from its slug only.
    """
    base = f"{vault.now():%Y-%m-%d}-{vault.slugify(title)}"
    slug = vault.unique_slug(base, lambda candidate: any(courses_dir().glob(f"*/{kind}/{candidate}.md")))
    return courses_dir() / course / kind / f"{slug}.md"


def find_document(kind: str, slug: str) -> Document:
    matches = sorted(courses_dir().glob(f"*/{kind}/{slug}.md"))
    if not matches:
        known = courses_dir().glob(f"*/{kind}/*.md")
        raise ToolError(f"Unknown {kind[:-1] if kind == 'exams' else 'class'} '{slug}'. Known : {_known(known)}.")
    return vault.read(matches[0])


def document_course(document: Document) -> str:
    """courses/<course>/<kind>/<slug>.md -> <course>"""
    return document.path.parent.parent.name


def iter_documents(course: str, kind: str) -> Iterator[Document]:
    """The classes or the exams of a course, in chronological order."""
    documents = [vault.read(path) for path in (courses_dir() / course / kind).glob("*.md")]
    documents.sort(key=lambda document: (vault.parse_time(document.metadata.get("created_at")) or datetime.min, document.slug))
    yield from documents


def iter_exams(course: str) -> Iterator[Document]:
    yield from iter_documents(course, "exams")


def mark_history(course: str) -> dict[str, list[int]]:
    """Marks of each skill, in chronological order of the exams."""
    history: dict[str, list[int]] = {}
    for exam in iter_exams(course):
        for evaluation in exam.metadata.get("skills") or []:
            if isinstance(evaluation, dict) and isinstance(evaluation.get("mark"), int):
                history.setdefault(str(evaluation.get("name")), []).append(evaluation["mark"])
    return history
