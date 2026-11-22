"""The plan of a course : the sequence of its classes and exams, thought through when the course is created.

Every step of the plan is a note of its own, created when the step is planned, in the folder of its
kind : `classes/class-<slug>.md`, `exams/quiz-<slug>.md` or `exams/exercise-<slug>.md`. Its properties
hold the plan, so that an Obsidian base shows it (see `dashboards.py`) :

    type : class | quiz | exercise    course : [[course-<course>]]    order : 1, 2, ...
    title, description, skills (links), importance : core | optional, status,
    added : true (a document created outside the plan), suggested_resources (titles and URLs)

A planned step has the status `planned` and a placeholder body. save_class and create_exam fill the
note of their step : a class is then `done`, an exam `assigned`, `filled` and `corrected`. A step
removed from the plan is deleted when nothing was written in it, and `dropped` otherwise.

Inside the tools, a step is a dict : {"slug", "kind" : class | quiz | project, "title", "description",
"skills", "importance", "resources", "added"}.
"""

from __future__ import annotations

from typing import Optional

from teach_me.database import blocks, objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

STEP_KINDS = ("class", "quiz", "project")
IMPORTANCES = ("core", "optional")
COURSE_STATUSES = ("active", "finished", "abandoned")
PROGRESS = ("planned", "in progress", "done")
"""planned : nothing done yet. in progress : an exam waiting for answers or for its correction. done : a class saved, an exam corrected."""
CLASSES_PER_EXAM = 3
"""The skill asks for at least one exam every 3 classes."""
NEXT_STEPS = 3
"""The number of steps to come returned with the state of a course."""
PLANNED, DROPPED = "planned", "dropped"
NOTE_TYPES = {"class": "class", "quiz": objects.EXAM_NOTE_TYPES["quiz"], "project": objects.EXAM_NOTE_TYPES["project"]}
"""The `type` of the note of each kind of step."""
KINDS = {note_type: kind for kind, note_type in NOTE_TYPES.items()}
PLACEHOLDER_BLOCK = "planned"


# --------------------------------------------------------------------------- #
# Reading the plan
# --------------------------------------------------------------------------- #


def step_notes(course: str, include_dropped: bool = False) -> list[Document]:
    """The notes of the steps of a course, in the order of the plan."""
    notes = []
    for folder in ("classes", "exams"):
        for path in (objects.courses_dir() / course / folder).glob("*.md"):
            document = vault.read(path)
            if document.metadata.get("type") not in KINDS:
                continue
            if document.metadata.get("status") == DROPPED and not include_dropped:
                continue
            notes.append(document)
    notes.sort(key=lambda document: (_order(document), document.path.stem))
    return notes


def _order(document: Document) -> float:
    value = document.metadata.get("order")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else float("inf")


def as_step(document: Document) -> dict:
    metadata = document.metadata
    step = {
        "slug": objects.slug(document),
        "kind": KINDS[metadata["type"]],
        "title": str(metadata.get("title") or objects.slug(document)),
        "description": str(metadata.get("description") or ""),
        "skills": [objects.unlink(skill) for skill in metadata.get("skills") or []],
        "importance": metadata.get("importance") if metadata.get("importance") in IMPORTANCES else "core",
    }
    if metadata.get("suggested_resources"):
        step["resources"] = list(metadata["suggested_resources"])
    if metadata.get("added"):
        step["added"] = True
    return step


def course_plan(course: Document) -> list[dict]:
    """The steps of the plan of a course, in order."""
    return [as_step(document) for document in step_notes(objects.course_slug(course))]


def status_progress(kind: str, status: Optional[str]) -> str:
    if status in (PLANNED, None):
        return "planned"
    if kind == "class":
        return "done"
    return "done" if status == "corrected" else "in progress"


def progress(course: str, step: dict) -> str:
    path = objects.step_file(course, step)
    if not path.is_file():
        return "planned"
    return status_progress(step["kind"], vault.read(path).metadata.get("status"))


def with_progress(course: str, steps: list[dict]) -> list[dict]:
    return [{**step, "progress": progress(course, step)} for step in steps]


def find_step(course: Document, slug: str) -> dict:
    steps = course_plan(course)
    for step in steps:
        if step["slug"] == slug:
            return step
    known = ", ".join(f"{step['slug']} ({step['kind']})" for step in steps) or "none"
    raise ToolError(f"Unknown step '{slug}' in the plan of '{objects.course_slug(course)}'. Steps : {known}.")


# --------------------------------------------------------------------------- #
# Slugs
# --------------------------------------------------------------------------- #


def reserved_slugs(folder: str) -> set[str]:
    """The slugs taken in a folder ("classes" or "exams") by a note of any course."""
    return {objects.slug(path) for path in objects.courses_dir().glob(f"*/{folder}/*.md")}


def new_slug(kind: str, title: str, taken: Optional[set[str]] = None) -> str:
    """A slug for a new step, unique among the steps of every course. Adds it to `taken`."""
    folder = objects.STEP_FOLDERS[kind]
    taken = reserved_slugs(folder) if taken is None else taken
    slug = vault.unique_slug(vault.slugify(title), lambda candidate: candidate in taken)
    taken.add(slug)
    return slug


# --------------------------------------------------------------------------- #
# Checking and changing the plan
# --------------------------------------------------------------------------- #


def clean_step(step: dict, course_skills: list[str], where: str) -> dict:
    """Validates a step given by the model, without its slug."""
    if not isinstance(step, dict):
        raise ToolError(f"{where} must be an object : {{kind, title, description, skills, importance}}.")
    kind, importance = step.get("kind"), step.get("importance", "core")
    if kind not in STEP_KINDS:
        raise ToolError(f"{where} : unknown kind '{kind}'. Use one of : {', '.join(STEP_KINDS)}.")
    if importance not in IMPORTANCES:
        raise ToolError(f"{where} : unknown importance '{importance}'. Use one of : {', '.join(IMPORTANCES)}.")
    title = str(step.get("title") or "").strip()
    if not title:
        raise ToolError(f"{where} needs a non empty `title`.")
    skills = check_step_skills(step.get("skills") or [], course_skills, f"{where} ('{title}')")
    cleaned = {"kind": kind, "title": title, "description": str(step.get("description") or "").strip(), "skills": skills, "importance": importance}
    resources = [str(resource).strip() for resource in step.get("resources") or [] if str(resource).strip()]
    if resources:
        cleaned["resources"] = resources
    return cleaned


def check_step_skills(skills: list, course_skills: list[str], where: str) -> list[str]:
    slugs = list(dict.fromkeys(objects.unlink(skill) for skill in skills))
    unknown = [skill for skill in slugs if skill not in course_skills]
    if unknown:
        raise ToolError(f"{where} : the course doesn't have the skills {', '.join(unknown)}. Skills of the course : {', '.join(course_skills) or 'none'}. Add them first (edit_course `add_skills`).")
    return slugs


def warnings(steps: list[dict], course_skills: list[str]) -> list[str]:
    """What a good plan should have : every skill evaluated by an exam, and an exam at least every 3 classes."""
    found = []
    exams = [step for step in steps if step["kind"] != "class"]
    evaluated = {skill for step in exams for skill in step["skills"]}
    missing = [skill for skill in course_skills if skill not in evaluated]
    if missing:
        found.append(f"No exam of the plan evaluates the skills {', '.join(missing)} : add exams for them, or add them to the skills of planned exams.")
    for step in exams:
        if not step["skills"]:
            found.append(f"The exam '{step['slug']}' evaluates no skill : give it the skills its questions will evaluate.")
    run: list[str] = []
    for step in [*steps, None]:
        if step is not None and step["kind"] == "class":
            run.append(step["slug"])
            continue
        if len(run) > CLASSES_PER_EXAM:
            found.append(f"{len(run)} classes in a row without an exam ({run[0]} → {run[-1]}) : plan an exercise at least every {CLASSES_PER_EXAM} classes.")
        run = []
    return found


def insert(steps: list[dict], new: list[dict], after: Optional[str]) -> list[dict]:
    """Inserts steps after the step `after`, first when it is "", at the end when it is None."""
    if after is None:
        return [*steps, *new]
    if after == "":
        return [*new, *steps]
    slugs = [step["slug"] for step in steps]
    if after not in slugs:
        raise ToolError(f"Unknown step '{after}' : steps of the plan : {', '.join(slugs) or 'none'}.")
    index = slugs.index(after) + 1
    return [*steps[:index], *new, *steps[index:]]


# --------------------------------------------------------------------------- #
# Writing the notes of the steps
# --------------------------------------------------------------------------- #


def placeholder(kind: str) -> str:
    """The body of the note of a planned step, until the step comes. What it is about is in its properties."""
    what = {"class": "This class", "quiz": "This quiz", "project": "This project exercise"}[kind]
    content = f"> [!todo] Planned\n> {what} comes later in the course : its content will be written here when its turn comes. What it covers is in its properties."
    return blocks.ensure_notes(blocks.render(PLACEHOLDER_BLOCK, content))


def _properties(step: dict, order: int) -> dict:
    """The properties of the plan, as written in the note of a step."""
    properties = {
        "title": step["title"],
        "description": step.get("description") or "",
        "order": order,
        "importance": step["importance"],
        "skills": [f"[[{objects.PREFIXES['skill']}{skill}]]" for skill in step["skills"]],
    }
    if step.get("resources"):
        properties["suggested_resources"] = list(step["resources"])
    if step.get("added"):
        properties["added"] = True
    return properties


def write_plan(course: str, steps: list[dict]) -> None:
    """Writes the plan : the notes of new steps are created as planned, the others get their new properties.

    The steps left out of `steps` are removed from the plan : deleted when nothing was written in them, dropped otherwise.
    """
    link = objects.course_link(course)
    kept = set()
    for order, step in enumerate(steps, 1):
        path = objects.step_file(course, step)
        kept.add(path)
        properties = _properties(step, order)
        if not path.is_file():
            moment = vault.format_time(vault.now())
            metadata = {"type": NOTE_TYPES[step["kind"]], "course": link, **properties, "status": PLANNED, "created_at": moment, "updated_at": moment}
            vault.write(Document(path, metadata, placeholder(step["kind"])))
            continue
        document = vault.read(path)
        metadata = {key: value for key, value in document.metadata.items() if key not in ("suggested_resources", "added")}
        merged = {"type": NOTE_TYPES[step["kind"]], "course": link, **metadata, **properties}
        if merged.get("status") == DROPPED:
            merged["status"] = PLANNED
        if merged != document.metadata:
            merged["updated_at"] = vault.format_time(vault.now())
            document.metadata = merged
            vault.write(document)
    for document in step_notes(course):
        if document.path not in kept:
            remove(document)


def remove(document: Document) -> None:
    """Removes a planned step from the plan : its note is deleted, unless the student wrote in it."""
    untouched = document.body.strip() == placeholder(as_step(document)["kind"]).strip()
    if untouched:
        document.path.unlink()
        return
    document.metadata["status"] = DROPPED
    document.metadata["updated_at"] = vault.format_time(vault.now())
    vault.write(document)


def fill(path, metadata: dict, content: str) -> Document:
    """Writes the document of a step in its note : the planned placeholder gives way to the content,
    and what the student wrote in the note in the meantime goes to its "My notes" section."""
    document = vault.read(path)
    rest = blocks.remove(document.body, PLACEHOLDER_BLOCK)
    notes = blocks.notes(rest)
    bounds = blocks.notes_bounds(rest)
    outside = (rest[:bounds[0]] + rest[bounds[1]:]).strip() if bounds else rest.strip()
    mine = "\n\n".join(text for text in (outside, notes) if text)
    body = content.strip("\n")
    if mine:
        body = f"{body}\n\n{blocks.NOTES_HEADING}\n\n{mine}"
    document.metadata = {**document.metadata, **metadata}
    document.body = body
    vault.write(document)
    return document


def add_unplanned(course: Document, kind: str, title: str, description: str, skills: list[str]) -> tuple[dict, str]:
    """Adds a document created outside the plan to the plan, after the last step started. Returns the step and a warning."""
    course_slug = objects.course_slug(course)
    steps = course_plan(course)
    step = {"slug": new_slug(kind, title), "kind": kind, "title": title, "description": description, "skills": skills, "importance": "optional", "added": True}
    started = [other["slug"] for other in steps if progress(course_slug, other) != "planned"]
    write_plan(course_slug, insert(steps, [step], started[-1] if started else ""))
    waiting = [f"{s['slug']} ('{s['title']}')" for s in steps if s["kind"] == kind and progress(course_slug, s) == "planned"]
    warning = f"'{title}' wasn't in the plan : it was added to it after the last step done."
    if waiting:
        warning += f" Next time, pass `planned` with one of the {kind} steps still to do : {', '.join(waiting[:5])}."
    return step, warning


def planned_step(course: Document, slug: str, kind: str) -> dict:
    """The step of the plan a new document is created for. It must be of the right kind and not done yet."""
    step = find_step(course, slug)
    if step["kind"] != kind:
        raise ToolError(f"The step '{slug}' is a {step['kind']}, not a {kind}.")
    if progress(objects.course_slug(course), step) != "planned":
        raise ToolError(f"The step '{slug}' already has its document ({vault.relative(objects.step_file(objects.course_slug(course), step))}). Leave `planned` out for a new one.")
    return step
