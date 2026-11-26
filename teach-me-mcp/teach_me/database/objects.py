"""The objects of the data model, and where they live in the vault.

    users/user-<user>.md
    projects/project-<project>.md
    skills/skill-<skill>.md                        (owned by a user, shared by their courses ; its grade and history)
    courses/<course>/course-<course>.md            (links to its skills and projects, the views of the course and the session log)
    courses/<course>/classes/class-<class>.md       (every step of the plan is a note, from the moment it is planned)
    courses/<course>/exams/quiz-<exam>.md          (questions, solutions and grades in .teach-me/)
    courses/<course>/exams/exercise-<exam>.md      (project exams)
    courses/<course>/resources/resource-<resource>.md

Every note has an `id` property (its file name, see `renames.py`) and a `type` property (user, project, skill, course, class, quiz, exercise, resource, or home for Home.md), and the
notes of a course a `course` property linking to it, so that Obsidian Bases can select them.

Obsidian finds a note by its file name, wherever it is : the prefix of each kind keeps the file names
unique in the whole vault, so that every link points to exactly one note. The tools only see the slugs,
without the prefix.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union

from teach_me.database import blocks, dashboards, quiz, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

SESSION_TIMEOUT = timedelta(hours=3)
"""A new session starts when the last activity on a course is older than this."""
SESSION_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})[ \t]*$", re.MULTILINE)
STEP_FOLDERS = {"class": "classes", "quiz": "exams", "project": "exams"}
"""Folder of the document of each kind of step of a plan."""
EXAM_TYPES = ("quiz", "project")
EXAM_STATUSES = ("assigned", "filled", "corrected")
EXAM_COEFFICIENTS = {"quiz": 1, "project": 2}
"""Weight of the questions of each type of exam in the grade of a skill."""
EXAM_NOTE_TYPES = {"quiz": "quiz", "project": "exercise"}
"""The `type` property of the note of each type of exam : a project exam is an exercise, 'project' is the type of the project notes."""
RESOURCE_STATUSES = ("new", "seen", "discussed", "dropped")
DOCUMENT_KINDS = ("classes", "exams")

PREFIXES = {
    "user": "user-",
    "project": "project-",
    "skill": "skill-",
    "course": "course-",
    "class": "class-",
    "quiz": "quiz-",
    "exercise": "exercise-",
    "resource": "resource-",
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


def resource_file(course: str, resource: str) -> Path:
    return courses_dir() / course / "resources" / f"{PREFIXES['resource']}{resource}.md"


def iter_resources(course: str) -> Iterator[Document]:
    """The resources shared in a course, in the order they were shared."""
    documents = vault.read_all((courses_dir() / course / "resources").glob(f"{PREFIXES['resource']}*.md"))
    documents.sort(key=lambda document: (vault.parse_time(document.metadata.get("created_at")) or datetime.min, document.path.stem))
    yield from documents


def slug(document: Union[Document, Path]) -> str:
    """The slug of a note : its file name, without the prefix of its kind."""
    stem = document.path.stem if isinstance(document, Document) else document.stem
    for prefix in sorted(PREFIXES.values(), key=len, reverse=True):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    return stem


def note_exam_type(document: Document) -> str:
    """The type of an exam, "quiz" or "project", as the `type` of its note says."""
    return "project" if document.metadata.get("type") in (EXAM_NOTE_TYPES["project"], "project") else "quiz"


def exam_type(document: Document) -> str:
    """The type of an exam, "quiz" or "project" : from its hidden data, the note only shows it."""
    data_type = exam_data(slug(document), strict=False).get("type")
    return data_type if data_type in EXAM_TYPES else note_exam_type(document)


# The hidden data of an exam (.teach-me/exams/<exam>.json) is the source of truth : the properties of its note
# (type, status, mean, questions, skills) only show it, and are written again from it whenever they differ,
# so that a hand edit in Obsidian can never change a grade.


def exam_facts(document: Document) -> Optional[dict]:
    """What the hidden data of an exam says about it : {"type", "status", "mean", "questions", "skills"}, or None for an exam
    not given yet (a planned step) or without data. Assigned or filled comes from the answers in the note."""
    data = exam_data(slug(document), strict=False)
    questions = data.get("questions") or []
    if not questions:
        return None
    kind = data.get("type") if data.get("type") in EXAM_TYPES else note_exam_type(document)
    grades = [question.get("grade") for question in questions]
    if data.get("corrected_at") and all(grade in quiz.GRADES for grade in grades):
        status, mean = "corrected", quiz.mean_score(grades)
    else:
        answered = any(answer is not None for answer in quiz.parse_answers(document.body, questions))
        status, mean = ("filled" if answered else "assigned"), None
    skills = list(dict.fromkeys(skill for question in questions for skill in question.get("skills") or []))
    return {"type": kind, "status": status, "mean": mean, "questions": len(questions), "skills": skills}


def exam_status(document: Document) -> Optional[str]:
    """The status of an exam : from its hidden data once it was given, from its note while it is only planned."""
    facts = exam_facts(document)
    return facts["status"] if facts else document.metadata.get("status")


def is_corrected(document: Document) -> bool:
    return exam_status(document) == "corrected"


def show_exam_facts(document: Document) -> list[str]:
    """Writes into the properties of an exam note what its hidden data says. Returns the properties that changed ; the caller writes the note."""
    facts = exam_facts(document)
    if facts is None:
        return []
    wanted = {
        "type": EXAM_NOTE_TYPES[facts["type"]],
        "status": facts["status"],
        "skills": [link_or_name("skill", skill, skill_file(skill)) for skill in facts["skills"]],
        "questions": facts["questions"],
        "mean": facts["mean"],
    }
    changed = [key for key, value in wanted.items() if document.metadata.get(key) != value]
    document.metadata.update({key: wanted[key] for key in changed})
    return changed


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
    yield from vault.read_all(sorted(users_dir().glob(f"{PREFIXES['user']}*.md")))


def get_project(project: str, user: Optional[str] = None) -> Document:
    """The note of a project. When it doesn't exist, the error lists the projects of `user` (of every user when None)."""
    path = project_file(project)
    if not path.is_file():
        raise ToolError(f"Unknown project '{project}'. Known projects : {_known(slug(document) for document in iter_projects(user))}. {HINTS['project']}")
    return vault.read(path)


def iter_projects(user: Optional[str]) -> Iterator[Document]:
    for document in vault.read_all(sorted(projects_dir().glob(f"{PREFIXES['project']}*.md"))):
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
    for document in vault.read_all(sorted(skills_dir().glob(f"{PREFIXES['skill']}*.md"))):
        if _owned_by(document, user):
            yield document


def exam_data_file(exam: str) -> Path:
    """The data of an exam that the student doesn't need to see : its questions (kind, skills, options, grade) and the grade of each skill."""
    return vault.vault_path() / ".teach-me" / "exams" / f"{exam}.json"


def exam_data(exam: str, strict: bool = True) -> dict:
    """{"questions": [{"kind", "skills", "options", "grade"}], "skills": {skill: {"grade", "score", "comment"}}, "corrected_at"}, or {} for an exam without data.

    Raises a ToolError when the file can't be read, unless `strict` is False : the exam is then skipped, with a warning."""
    try:
        data = vault.read_json(exam_data_file(exam), {})
    except ToolError as error:
        if strict:
            raise
        vault.warn(f"Skipped the data of the exam '{exam}' : {error}")
        return {}
    return data if isinstance(data, dict) else {}


def write_exam_data(exam: str, data: dict) -> None:
    vault.write_json(exam_data_file(exam), data)


def skill_grades(user: str) -> dict[str, dict]:
    """Grade of each skill of a user : {"grade", "score", "history", "evaluations"}.

    The score is the weighted mean of the grades of every question that evaluates the skill, in the
    corrected exams of all the courses (a project exam weighs twice a quiz), and the grade is the letter
    closest to it. The history holds the grade of the skill in each exam, in chronological order, and
    the evaluations the details of each : {"exam", "path", "title", "course", "date", "grade", "score", "comment"}.
    """
    exams = [exam for course in iter_courses(user) for exam in iter_exams(course_slug(course))]
    exams = [(exam, exam_data(slug(exam), strict=False)) for exam in exams if is_corrected(exam)]
    exams.sort(key=lambda pair: vault.parse_time(pair[1].get("corrected_at")) or vault.parse_time(pair[0].metadata.get("created_at")) or datetime.min)  # stable : keeps the order of each course
    totals: dict[str, list[float]] = {}
    evaluations: dict[str, list[dict]] = {}
    for exam, data in exams:
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
        course_name = next((document.metadata.get("name") for document in vault.read_all([course] if course.is_file() else [])), None)
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


def refresh_derived(user: str) -> list[str]:
    """Writes again every value the tools can deduce from their hidden data, in case the student changed it by hand :
    the properties of the exam notes, then the grades and histories of the skill notes. Returns one line per note changed."""
    changed = []
    for course in iter_courses(user):
        for exam in iter_exams(course_slug(course)):
            fixed = show_exam_facts(exam)
            if fixed:
                vault.write(exam)
                changed.append(f"{vault.relative(exam.path)} : {', '.join(fixed)}")
    changed += [f"{vault.relative(skill_file(skill))} : grade and history" for skill in refresh_skills(user)]
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
    paths = [path for path in sorted(courses_dir().glob(f"*/{PREFIXES['course']}*.md")) if path.stem == f"{PREFIXES['course']}{path.parent.name}"]
    for document in vault.read_all(paths):
        if _owned_by(document, user):
            yield document


def last_activity(document: Document) -> Optional[datetime]:
    metadata = document.metadata
    return vault.parse_time(metadata.get("updated_at")) or vault.parse_time(metadata.get("created_at"))


def as_list(value) -> list[str]:
    """A list property as the tools wrote it, even after a hand edit : a single text (Obsidian's property panel can turn a list
    into one) is a list of one item, empty items are left out."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(item) for item in items if item is not None and not isinstance(item, (dict, list)) and str(item).strip()]


def linked_note(kind: str, target: str, path: Path) -> Optional[Document]:
    """The note a course links to, or None (with a warning) when it is missing or can't be read : the caller goes on without it."""
    if not path.is_file():
        link_or_name(kind, target, path)
        return None
    found = vault.read_all([path])
    return found[0] if found else None


def course_skills(course: Document) -> list[str]:
    """The slugs of the skills a course evaluates, in the order they were declared."""
    return list(dict.fromkeys(unlink(skill) for skill in as_list(course.metadata.get("skills"))))


def course_projects(course: Document) -> list[str]:
    """The slugs of the projects a course builds towards."""
    return list(dict.fromkeys(unlink(project) for project in as_list(course.metadata.get("projects"))))


def link_or_name(kind: str, target: str, path: Path, alias: Optional[str] = None) -> str:
    """The link to the note of an object, or its link text when the note is missing (deleted or renamed by the student), with a warning.
    For the places where a missing note must not stop the tool : the link shows as unresolved in Obsidian until the note is back."""
    if path.is_file():
        return link(kind, target, path, alias)
    vault.warn(
        f"The {kind} note {vault.relative(path)} is missing (deleted or renamed in Obsidian) : the tools kept working without it. "
        "start_session puts back a note renamed or moved in Obsidian : if it is still missing after start_session, it was deleted (or renamed before it had an `id`). "
        "Ask the student, then rename it back, create it again, or remove it from the course with edit_course."
    )
    return f"[[{path.stem}|{alias}]]" if alias else f"[[{path.stem}]]"


def step_prefix(kind: str) -> str:
    """File prefix of the document of a step : class-, quiz- or exercise-."""
    return PREFIXES["class"] if kind == "class" else EXAM_PREFIXES[kind]


def step_file(course: str, step: dict) -> Path:
    """Where the document of a step of the plan is, or will be."""
    return courses_dir() / course / STEP_FOLDERS[step["kind"]] / f"{step_prefix(step['kind'])}{step['slug']}.md"


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


def iter_documents(course: str, kind: str) -> Iterator[Document]:
    """The classes or the exams of a course that were given (not only planned), in chronological order : by date, then in the order of the plan."""
    documents = vault.read_all((courses_dir() / course / kind).glob("*.md"))
    documents = [document for document in documents if document.metadata.get("status") not in ("planned", "dropped") or exam_facts(document)]
    documents.sort(
        key=lambda document: (
            vault.parse_time(document.metadata.get("started_at")) or vault.parse_time(document.metadata.get("created_at")) or datetime.min,
            document.metadata.get("order") if isinstance(document.metadata.get("order"), int) else 0,
            document.path.stem,
        )
    )
    yield from documents


def iter_exams(course: str) -> Iterator[Document]:
    yield from iter_documents(course, "exams")


INTERFACES = ("terminal", "app")
"""The interfaces a user has preferences for."""
USER_PROPERTIES = ("id", "type", "name", "aliases", "created_at", "updated_at", "known_skills")
"""The properties of a user note that aren't preferences."""
SKILL_SEPARATOR = " : "
"""Between the name and the description of a known skill : `known_skills` is a list of texts, e.g. "python : numpy and pandas"."""

# The user note stores everything flat, so that Obsidian shows it and Bases can read it :
#     language: french              a preference that doesn't depend on the interface
#     terminal_quizzes: vault       a preference of one interface, prefixed by its name
#     known_skills: ["python : numpy and pandas"]
# The tools keep giving and taking them as dictionaries, as before.


def read_preferences(metadata: dict) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """The preferences of a user note : (general, {interface: preferences})."""
    general: dict[str, str] = {}
    interfaces: dict[str, dict[str, str]] = {}
    for key, value in metadata.items():
        if key in USER_PROPERTIES or value is None:
            continue
        interface = next((name for name in INTERFACES if key.startswith(f"{name}_")), None)
        if interface:
            interfaces.setdefault(interface, {})[key.removeprefix(f"{interface}_")] = str(value)
        else:
            general[key] = str(value)
    return general, interfaces


def write_preferences(metadata: dict, general: dict[str, str], interfaces: dict[str, dict[str, str]]) -> dict:
    """The properties of a user note with these preferences, after its own properties and before its known skills."""
    own = {key: metadata[key] for key in USER_PROPERTIES if key in metadata and key != "known_skills"}
    flat = {f"{interface}_{key}": value for interface in INTERFACES for key, value in (interfaces.get(interface) or {}).items()}
    return {**own, **general, **flat, "known_skills": metadata.get("known_skills") or []}


def read_known_skills(metadata: dict) -> list[dict]:
    skills = []
    for item in metadata.get("known_skills") or []:
        if isinstance(item, dict):  # notes written before migration 2
            skills.append({"name": str(item.get("name") or ""), "description": str(item.get("description") or "")})
        else:
            name, _, description = str(item).partition(SKILL_SEPARATOR)
            skills.append({"name": name.strip(), "description": description.strip()})
    return skills


def write_known_skills(skills: list[dict]) -> list[str]:
    return [f"{skill['name']}{SKILL_SEPARATOR}{skill['description']}" if skill.get("description") else skill["name"] for skill in skills]


PROGRESS_HEADING = "## Progress"


def split_project(body: str) -> tuple[str, str, str]:
    """A project note holds its views (generated), its description, the "## Progress" log, then the student's "My notes" section.
    Returns the description, the log and the "My notes" section. A version of the views the student edited moves to "My notes" first."""
    body = blocks.replace(body, dashboards.PROJECT_BLOCK, dashboards.PROJECT_DASHBOARD, vault.format_session(vault.now()), first=True)
    body = blocks.remove(body, dashboards.PROJECT_BLOCK)
    bounds = blocks.notes_bounds(body)
    notes = body[bounds[0]:bounds[1]].strip() if bounds else ""
    if bounds:
        body = body[:bounds[0]] + body[bounds[1]:]
    description, _, progress = body.partition(PROGRESS_HEADING)
    return description.strip(), progress.strip(), notes


def write_project(document: Document, description: str, log: str, notes: str) -> None:
    """Writes a project note : its views, then its description, its progress log and "My notes"."""
    body = description + (f"\n\n{PROGRESS_HEADING}\n\n{log}" if log else "") + (f"\n\n{notes}" if notes else "")
    document.body = blocks.ensure_notes(body.strip("\n"))
    dashboards.render_project(document)
    vault.write(document)


def render_project(project: str) -> None:
    """Writes the views of a project note again, when the student broke them. A missing or unreadable project is skipped, with a warning."""
    document = linked_note("project", project, project_file(project))
    if document is None:
        return
    before = document.body
    dashboards.render_project(document)
    if document.body != before:
        vault.write(document)
