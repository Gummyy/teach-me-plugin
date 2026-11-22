"""The objects of the data model, and where they live in the vault.

    users/user-<user>.md
    projects/project-<project>.md
    skills/skill-<skill>.md                        (owned by a user, shared by their courses ; its grade and history)
    courses/<course>/course-<course>.md            (links to its skills, its plan and the session log)
    courses/<course>/classes/class-<class>.md
    courses/<course>/exams/quiz-<exam>.md          (questions, solutions and grades in .teach-me/)
    courses/<course>/exams/exercise-<exam>.md      (project exams)
    courses/<course>/report-card-<course>.md       (generated)

Every note has a `type` property (user, project, skill, course, class, quiz or exercise), and the
notes of a course a `course` property linking to it, so that Obsidian Bases can select them.

Obsidian finds a note by its file name, wherever it is : the prefix of each kind keeps the file names
unique in the whole vault, so that every link points to exactly one note. The tools only see the slugs,
without the prefix.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union

from teach_me.database import blocks, quiz, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

SESSION_TIMEOUT = timedelta(hours=3)
"""A new session starts when the last activity on a course is older than this."""
SESSION_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})[ \t]*$", re.MULTILINE)
CONTENT_HEADING = "## Content"
"""The section that listed the classes and exams of a course before the plan replaced it."""
PLAN_HEADING = "## Plan"
"""The section of course.md showing its plan as a table. It comes before the session log."""
STEP_FOLDERS = {"class": "classes", "quiz": "exams", "project": "exams"}
"""Folder of the document of each kind of step of a plan."""
EXAM_TYPES = ("quiz", "project")
EXAM_STATUSES = ("assigned", "filled", "corrected")
EXAM_COEFFICIENTS = {"quiz": 1, "project": 2}
"""Weight of the questions of each type of exam in the grade of a skill."""
EXAM_NOTE_TYPES = {"quiz": "quiz", "project": "exercise"}
"""The `type` property of the note of each type of exam : a project exam is an exercise, 'project' is the type of the project notes."""
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


def exam_type(document: Document) -> str:
    """The type of an exam, "quiz" or "project", from the `type` of its note."""
    return "project" if document.metadata.get("type") in (EXAM_NOTE_TYPES["project"], "project") else "quiz"


def course_link(course: str) -> str:
    """The link to the note of a course, written in the `course` property of its classes and exams."""
    return link("course", course, course_file(course))


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


def _known(slugs: Iterable[str], limit: int = 20) -> str:
    names = sorted(slugs)
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
        raise ToolError(f"Unknown user '{user}'. Known users : {_known(slug(path) for path in users_dir().glob(PREFIXES['user'] + '*.md'))}. {HINTS['user']}")
    return vault.read(path)


def iter_users() -> Iterator[Document]:
    for path in sorted(users_dir().glob(f"{PREFIXES['user']}*.md")):
        yield vault.read(path)


def get_project(project: str, user: Optional[str] = None) -> Document:
    """The note of a project. When it doesn't exist, the error lists the projects of `user` (of every user when None)."""
    path = project_file(project)
    if not path.is_file():
        raise ToolError(f"Unknown project '{project}'. Known projects : {_known(slug(document) for document in iter_projects(user))}. {HINTS['project']}")
    return vault.read(path)


def iter_projects(user: Optional[str]) -> Iterator[Document]:
    for path in sorted(projects_dir().glob(f"{PREFIXES['project']}*.md")):
        document = vault.read(path)
        if _owned_by(document, user):
            yield document


# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #


def get_skill(skill: str, user: Optional[str] = None) -> Document:
    """The note of a skill. When it doesn't exist, the error lists the skills of `user` (of every user when None)."""
    path = skill_file(skill)
    if not path.is_file():
        raise ToolError(f"Unknown skill '{skill}'. Known skills : {_known(slug(document) for document in iter_skills(user))}. {HINTS['skill']}")
    return vault.read(path)


def iter_skills(user: Optional[str]) -> Iterator[Document]:
    for path in sorted(skills_dir().glob(f"{PREFIXES['skill']}*.md")):
        document = vault.read(path)
        if _owned_by(document, user):
            yield document


def exam_data_file(exam: str) -> Path:
    """The data of an exam that the student doesn't need to see : its questions (kind, skills, options, grade) and the grade of each skill."""
    return vault.vault_path() / ".teach-me" / "exams" / f"{exam}.json"


def exam_data(exam: str) -> dict:
    """{"questions": [{"kind", "skills", "options", "grade"}], "skills": {skill: {"grade", "score", "comment"}}, "corrected_at"}, or {} for an exam without data."""
    file = exam_data_file(exam)
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}


def write_exam_data(exam: str, data: dict) -> None:
    file = exam_data_file(exam)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def skill_grades(user: str) -> dict[str, dict]:
    """Grade of each skill of a user : {"grade", "score", "history", "evaluations"}.

    The score is the weighted mean of the grades of every question that evaluates the skill, in the
    corrected exams of all the courses (a project exam weighs twice a quiz), and the grade is the letter
    closest to it. The history holds the grade of the skill in each exam, in chronological order, and
    the evaluations the details of each : {"exam", "path", "title", "course", "date", "grade", "score", "comment"}.
    """
    exams = [exam for course in iter_courses(user) for exam in iter_exams(course_slug(course))]
    exams.sort(key=lambda document: vault.parse_time(document.metadata.get("created_at")) or datetime.min)  # stable : keeps the order of each course
    totals: dict[str, list[float]] = {}
    evaluations: dict[str, list[dict]] = {}
    for exam in exams:
        if exam.metadata.get("status") != "corrected":
            continue
        data = exam_data(slug(exam))
        coefficient = EXAM_COEFFICIENTS[exam_type(exam)]
        for question in data.get("questions") or []:
            if question.get("grade") not in quiz.GRADES:
                continue
            for skill in question.get("skills") or []:
                total = totals.setdefault(skill, [0.0, 0.0])
                total[0] += coefficient * quiz.GRADES[question["grade"]]["value"]
                total[1] += coefficient
        for skill, evaluation in (data.get("skills") or {}).items():
            if evaluation.get("grade") in quiz.GRADES:
                evaluations.setdefault(skill, []).append(
                    {
                        "exam": slug(exam),
                        "path": exam.path,
                        "title": str(exam.metadata.get("title") or slug(exam)),
                        "course": document_course(exam),
                        "date": data.get("corrected_at") or exam.metadata.get("updated_at"),
                        **{key: evaluation.get(key) for key in ("grade", "score", "comment")},
                    }
                )
    grades = {}
    for skill, (weighted, weights) in totals.items():
        score = round(weighted / weights, 2)
        found = evaluations.get(skill, [])
        grades[skill] = {"grade": quiz.grade_of(score), "score": score, "history": [e["grade"] for e in found], "evaluations": found}
    return grades


HISTORY_BLOCK = "history"
"""The generated block of a skill note : its grade in every exam that evaluated it."""


def _cell(value) -> str:
    return " ".join(str(value if value is not None else "").replace("|", "\\|").split())


def history_table(evaluations: list[dict]) -> str:
    lines = ["## 📈 History", ""]
    if not evaluations:
        return "\n".join(lines + ["Not evaluated yet : the grades of the exams that evaluate this skill will show here."])
    lines += ["| Date | Exam | Course | Grade | Score | Comment |", "| --- | --- | --- | --- | --- | --- |"]
    for evaluation in evaluations:
        moment = vault.parse_time(evaluation["date"])
        course = course_file(evaluation["course"])
        course_name = vault.read(course).metadata.get("name") if course.is_file() else evaluation["course"]
        exam_link = link("exam", evaluation["exam"], evaluation["path"], alias=evaluation["title"]).replace("|", "\\|")
        course_link_text = link("course", evaluation["course"], course, alias=str(course_name or evaluation["course"])).replace("|", "\\|")
        lines.append(
            f"| {f'{moment:%Y-%m-%d}' if moment else ''} | {exam_link} | {course_link_text} | {evaluation['grade']} | "
            f"{evaluation['score']}/5 | {_cell(evaluation.get('comment'))} |"
        )
    return "\n".join(lines)


def skill_body(body: str, evaluations: list[dict]) -> str:
    """The body of a skill note with its history rewritten and a "My notes" section."""
    return blocks.ensure_notes(blocks.replace(body, HISTORY_BLOCK, history_table(evaluations), vault.format_session(vault.now())))


def refresh_skills(user: str, skills: Optional[Iterable[str]] = None) -> list[str]:
    """Writes the grade of each skill of a user (or only of `skills`) in its note : the properties grade, score,
    evaluations, last_evaluated and progression, and the history table. Returns the slugs of the notes changed."""
    grades = skill_grades(user)
    wanted = None if skills is None else set(skills)
    changed = []
    for document in iter_skills(user):
        name = slug(document)
        if wanted is not None and name not in wanted:
            continue
        grade = grades.get(name) or {}
        found = grade.get("evaluations") or []
        metadata = {
            **document.metadata,
            "grade": grade.get("grade"),
            "score": grade.get("score"),
            "evaluations": len(found),
            "last_evaluated": found[-1]["date"] if found else None,
            "progression": " → ".join(grade.get("history") or []) or None,
        }
        body = skill_body(document.body, found)
        if metadata != document.metadata or body != document.body:
            document.metadata, document.body = metadata, body
            vault.write(document)
            changed.append(name)
    return changed


# --------------------------------------------------------------------------- #
# Courses
# --------------------------------------------------------------------------- #


def get_course(course: str, user: Optional[str] = None) -> Document:
    """The note of a course. When it doesn't exist, the error lists the courses of `user` (of every user when None)."""
    path = course_file(course)
    if not path.is_file():
        raise ToolError(f"Unknown course '{course}'. Known courses : {_known(course_slug(document) for document in iter_courses(user))}. {HINTS['course']}")
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


def step_prefix(kind: str) -> str:
    """File prefix of the document of a step : class-, quiz- or exercise-."""
    return PREFIXES["class"] if kind == "class" else EXAM_PREFIXES[kind]


def step_file(course: str, step: dict) -> Path:
    """Where the document of a step of the plan is, or will be."""
    return courses_dir() / course / STEP_FOLDERS[step["kind"]] / f"{step_prefix(step['kind'])}{step['slug']}.md"


def section(body: str, heading: str) -> Optional[tuple[int, int]]:
    """Start and end of a "## " section of a body, heading included, or None."""
    match = re.search(rf"^{re.escape(heading)}[ \t]*$", body, re.MULTILINE)
    if match is None:
        return None
    following = re.search(r"^## ", body[match.end():], re.MULTILINE)
    return match.start(), match.end() + following.start() if following else len(body)


def legacy_content(body: str) -> list[tuple[str, Optional[str]]]:
    """The (file name, alias) of the notes linked in the "## Content" section of a course created before the plans."""
    bounds = section(body, CONTENT_HEADING)
    if bounds is None:
        return []
    links = re.findall(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]", body[bounds[0]:bounds[1]])
    return list(dict.fromkeys((stem.strip(), alias.strip() or None) for stem, alias in links))


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


def find_document(kind: str, target: str) -> Document:
    matches = sorted(path for prefix in _document_prefixes(kind) for path in courses_dir().glob(f"*/{kind}/{prefix}{target}.md"))
    if not matches:
        name = "exam" if kind == "exams" else "class"
        known = (slug(path) for path in courses_dir().glob(f"*/{kind}/*.md"))
        raise ToolError(f"Unknown {name} '{target}'. Known : {_known(known)}. {HINTS[name]}")
    return vault.read(matches[0])


def document_course(document: Document) -> str:
    """courses/<course>/<kind>/<file>.md -> <course>"""
    return document.path.parent.parent.name


def content_order(course: str) -> dict[str, int]:
    """Position of each class and exam in the plan of a course (or its old "## Content" section), by file name."""
    document = get_course(course)
    plan = [step for step in document.metadata.get("plan") or [] if isinstance(step, dict) and step.get("kind") in STEP_FOLDERS]
    stems = [f"{step_prefix(step['kind'])}{step.get('slug')}" for step in plan] or [stem for stem, _ in legacy_content(document.body)]
    return {stem: index for index, stem in enumerate(dict.fromkeys(stems))}


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
