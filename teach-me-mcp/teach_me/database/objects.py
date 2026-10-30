"""The objects of the data model, and where they live in the vault.

    users/user-<user>.md
    projects/project-<project>.md
    skills/skill-<skill>.md                        (owned by a user, shared by their courses)
    courses/<course>/course-<course>.md            (links to its skills, ordered content and the session log)
    courses/<course>/classes/class-<class>.md
    courses/<course>/exams/quiz-<exam>.md          (evaluations in the frontmatter)
    courses/<course>/exams/exercise-<exam>.md      (project exams)
    courses/<course>/report-card-<course>.md       (generated)

Obsidian finds a note by its file name, wherever it is : the prefix of each kind keeps the file names
unique in the whole vault, so that every link points to exactly one note. The tools only see the slugs,
without the prefix.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional, Union

from teach_me.database import quiz, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

SESSION_TIMEOUT = timedelta(hours=3)
"""A new session starts when the last activity on a course is older than this."""
SESSION_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})[ \t]*$", re.MULTILINE)
CONTENT_HEADING = "## Content"
"""The section of course.md listing its classes and exams, in order. It comes before the session log."""
EXAM_TYPES = ("quiz", "project")
EXAM_STATUSES = ("assigned", "filled", "corrected")
EXAM_COEFFICIENTS = {"quiz": 1, "project": 2}
"""Weight of the questions of each type of exam in the grade of a skill."""
RESOURCE_STATUSES = ("new", "explained", "unprocessed")
DOCUMENT_KINDS = ("classes", "exams")

PREFIXES = {
    "user": "user-",
    "project": "project-",
    "skill": "skill-",
    "course": "course-",
    "report": "report-card-",
    "class": "class-",
    "quiz": "quiz-",
    "exercise": "exercise-",
}
EXAM_PREFIXES = {"quiz": PREFIXES["quiz"], "project": PREFIXES["exercise"]}
"""File prefix of each type of exam. 'project-' is taken by the projects."""
HINTS = {
    "user": "Use the slug returned by list_users or create_user.",
    "project": "Create it first with create_project.",
    "skill": "Create it first with create_skills.",
    "course": "Use the slug returned by list_courses or create_course.",
    "class": "Use the slug returned by save_class.",
    "exam": "Use the slug returned by create_exam.",
}


# --------------------------------------------------------------------------- #
# Folders, file names and links
# --------------------------------------------------------------------------- #


def users_dir() -> Path:
    return vault.vault_path() / "users"


def projects_dir() -> Path:
    return vault.vault_path() / "projects"


def skills_dir() -> Path:
    return vault.vault_path() / "skills"


def courses_dir() -> Path:
    return vault.vault_path() / "courses"


def user_file(user: str) -> Path:
    return users_dir() / f"{PREFIXES['user']}{user}.md"


def project_file(project: str) -> Path:
    return projects_dir() / f"{PREFIXES['project']}{project}.md"


def skill_file(skill: str) -> Path:
    return skills_dir() / f"{PREFIXES['skill']}{skill}.md"


def course_file(course: str) -> Path:
    return courses_dir() / course / f"{PREFIXES['course']}{course}.md"


def report_file(course: str) -> Path:
    return courses_dir() / course / f"{PREFIXES['report']}{course}.md"


def slug(document: Union[Document, Path]) -> str:
    """The slug of a note : its file name, without the prefix of its kind."""
    stem = document.path.stem if isinstance(document, Document) else document.stem
    for prefix in sorted(PREFIXES.values(), key=len, reverse=True):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    return stem


def unlink(value) -> str:
    """'[[skill-convolution]]' -> 'convolution'"""
    return slug(Path(vault.unlink(value)))


def link(kind: str, target: str, path: Path, alias: Optional[str] = None) -> str:
    """Obsidian link to the note of an object. Raises a ToolError when the note doesn't exist."""
    try:
        text = vault.link(path)
    except vault.LinkError:
        raise ToolError(f"Unknown {kind} '{target}' : there is no note at {vault.relative(path)}. {HINTS.get(kind, '')}".rstrip()) from None
    if not alias:
        return text
    alias = " ".join(alias.replace("|", "/").replace("[", "(").replace("]", ")").split())  # an alias can't contain | [ ]
    return f"{text[:-2]}|{alias}]]"


def _known(paths: Iterator[Path], limit: int = 20) -> str:
    names = sorted(slug(path) for path in paths)
    if not names:
        return "none"
    return ", ".join(names[:limit]) + (", ..." if len(names) > limit else "")


def _owned_by(document: Document, user: Optional[str]) -> bool:
    return user is None or unlink(document.metadata.get("user", "")) == user


# --------------------------------------------------------------------------- #
# Users and projects
# --------------------------------------------------------------------------- #


def get_user(user: str) -> Document:
    path = user_file(user)
    if not path.is_file():
        raise ToolError(f"Unknown user '{user}'. Known users : {_known(users_dir().glob('*.md'))}. {HINTS['user']}")
    return vault.read(path)


def iter_users() -> Iterator[Document]:
    for path in sorted(users_dir().glob(f"{PREFIXES['user']}*.md")):
        yield vault.read(path)


def get_project(project: str) -> Document:
    path = project_file(project)
    if not path.is_file():
        raise ToolError(f"Unknown project '{project}'. Known projects : {_known(projects_dir().glob('*.md'))}. {HINTS['project']}")
    return vault.read(path)


def iter_projects(user: str) -> Iterator[Document]:
    for path in sorted(projects_dir().glob(f"{PREFIXES['project']}*.md")):
        document = vault.read(path)
        if _owned_by(document, user):
            yield document


# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #


def get_skill(skill: str) -> Document:
    path = skill_file(skill)
    if not path.is_file():
        raise ToolError(f"Unknown skill '{skill}'. Known skills : {_known(skills_dir().glob('*.md'))}. {HINTS['skill']}")
    return vault.read(path)


def iter_skills(user: str) -> Iterator[Document]:
    for path in sorted(skills_dir().glob(f"{PREFIXES['skill']}*.md")):
        document = vault.read(path)
        if _owned_by(document, user):
            yield document


def skill_grades(user: str) -> dict[str, dict]:
    """Grade of each skill of a user : {"grade", "score", "history"}.

    The score is the weighted mean of the grades of every question that evaluates the skill, in the
    corrected exams of all the courses (a project exam weighs twice a quiz), and the grade is the letter
    closest to it. The history holds the grade of the skill in each exam, in chronological order.
    """
    exams = [exam for course in iter_courses(user) for exam in iter_exams(course_slug(course))]
    exams.sort(key=lambda document: vault.parse_time(document.metadata.get("created_at")) or datetime.min)  # stable : keeps the order of each course
    totals: dict[str, list[float]] = {}
    history: dict[str, list[str]] = {}
    for exam in exams:
        if exam.metadata.get("status") != "corrected":
            continue
        coefficient = EXAM_COEFFICIENTS.get(exam.metadata.get("type"), 1)
        for question in exam.metadata.get("questions") or []:
            if question.get("grade") not in quiz.GRADES:
                continue
            for skill in question.get("skills") or []:
                total = totals.setdefault(skill, [0.0, 0.0])
                total[0] += coefficient * quiz.GRADES[question["grade"]]["value"]
                total[1] += coefficient
        for evaluation in exam.metadata.get("skills") or []:
            if isinstance(evaluation, dict) and evaluation.get("grade") in quiz.GRADES:
                history.setdefault(unlink(evaluation.get("skill", "")), []).append(evaluation["grade"])
    grades = {}
    for skill, (weighted, weights) in totals.items():
        score = round(weighted / weights, 2)
        grades[skill] = {"grade": quiz.grade_of(score), "score": score, "history": history.get(skill, [])}
    return grades


# --------------------------------------------------------------------------- #
# Courses
# --------------------------------------------------------------------------- #


def get_course(course: str) -> Document:
    path = course_file(course)
    if not path.is_file():
        courses = (p.parent for p in courses_dir().glob(f"*/{PREFIXES['course']}*.md"))
        raise ToolError(f"Unknown course '{course}'. Known courses : {_known(courses)}. {HINTS['course']}")
    return vault.read(path)


def course_slug(document: Document) -> str:
    """The slug of a course is the name of its folder."""
    return document.path.parent.name


def iter_courses(user: Optional[str] = None) -> Iterator[Document]:
    for path in sorted(courses_dir().glob(f"*/{PREFIXES['course']}*.md")):
        if path.stem != f"{PREFIXES['course']}{path.parent.name}":
            continue
        document = vault.read(path)
        if _owned_by(document, user):
            yield document


def last_activity(document: Document) -> Optional[datetime]:
    metadata = document.metadata
    return vault.parse_time(metadata.get("updated_at")) or vault.parse_time(metadata.get("created_at"))


def course_skills(course: Document) -> list[str]:
    """The slugs of the skills a course evaluates, in the order they were declared."""
    return [unlink(skill) for skill in course.metadata.get("skills") or [] if isinstance(skill, str)]


def add_to_content(course: Document, entry: str) -> None:
    """Appends a numbered entry to the "## Content" section of a course. The caller must write the document."""
    body = course.body
    if CONTENT_HEADING not in body:
        body = f"{CONTENT_HEADING}\n\n{body.lstrip()}"
    start = body.index(CONTENT_HEADING) + len(CONTENT_HEADING)
    following = re.search(r"^## ", body[start:], re.MULTILINE)
    end = start + following.start() if following else len(body)
    section = body[start:end].strip("\n")
    number = len(re.findall(r"^\d+\. ", section, re.MULTILINE)) + 1
    section = f"{section}\n{number}. {entry}".strip("\n")
    rest = body[end:].lstrip("\n")
    course.body = f"{body[:start]}\n\n{section}\n" + (f"\n{rest}" if rest else "")


# --------------------------------------------------------------------------- #
# Sessions : dated entries in the body of course.md, after its content
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


def _document_prefixes(kind: str) -> list[str]:
    return [PREFIXES["class"]] if kind == "classes" else list(EXAM_PREFIXES.values())


def new_document_path(course: str, kind: str, title: str, exam_type: Optional[str] = None) -> Path:
    """Path of a new class / exam : courses/<course>/<kind>/<prefix><title>.md

    Slugs are unique in the whole vault (across courses, and across quizzes and project exams), so that
    tools can find a document from its slug only. The date of the document is in its frontmatter.
    """
    prefixes = _document_prefixes(kind)
    candidate = vault.unique_slug(
        vault.slugify(title),
        lambda candidate: any(any(courses_dir().glob(f"*/{kind}/{prefix}{candidate}.md")) for prefix in prefixes),
    )
    prefix = EXAM_PREFIXES[exam_type] if kind == "exams" else PREFIXES["class"]
    return courses_dir() / course / kind / f"{prefix}{candidate}.md"


def find_document(kind: str, target: str) -> Document:
    matches = sorted(path for prefix in _document_prefixes(kind) for path in courses_dir().glob(f"*/{kind}/{prefix}{target}.md"))
    if not matches:
        name = "exam" if kind == "exams" else "class"
        known = courses_dir().glob(f"*/{kind}/*.md")
        raise ToolError(f"Unknown {name} '{target}'. Known : {_known(known)}. {HINTS[name]}")
    return vault.read(matches[0])


def document_course(document: Document) -> str:
    """courses/<course>/<kind>/<file>.md -> <course>"""
    return document.path.parent.parent.name


def content_order(course: str) -> dict[str, int]:
    """Position of each note linked in the "## Content" section of a course, by file name."""
    body = get_course(course).body
    if CONTENT_HEADING not in body:
        return {}
    section = body[body.index(CONTENT_HEADING) + len(CONTENT_HEADING):]
    following = re.search(r"^## ", section, re.MULTILINE)
    section = section[: following.start()] if following else section
    order: dict[str, int] = {}
    for stem in re.findall(r"\[\[([^\]|#]+)", section):
        order.setdefault(stem.strip(), len(order))
    return order


def iter_documents(course: str, kind: str) -> Iterator[Document]:
    """The classes or the exams of a course, in chronological order : by date, then in the order of the content of the course."""
    order = content_order(course)
    documents = [vault.read(path) for path in (courses_dir() / course / kind).glob("*.md")]
    documents.sort(
        key=lambda document: (
            vault.parse_time(document.metadata.get("created_at")) or datetime.min,
            order.get(document.path.stem, len(order)),
            document.path.stem,
        )
    )
    yield from documents


def iter_exams(course: str) -> Iterator[Document]:
    yield from iter_documents(course, "exams")
