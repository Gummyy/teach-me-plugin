"""The plan of a course : the sequence of its classes and exams, thought through when the course is created.

The plan lives in the frontmatter of course.md (`plan`), and is shown as a table in its "## Plan"
section, with links to the documents of its steps, which don't exist until the step is done. Each step
gets its slug when it is planned, so that save_class and create_exam create exactly the file the table
links to. The progress of a step is never stored : it comes from the documents that exist.

    {"slug", "kind" : class | quiz | project, "title", "description", "skills", "importance" : core | optional,
     "resources" (optional), "added" (true for a document created outside the plan)}
"""

from __future__ import annotations

from typing import Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

STEP_KINDS = ("class", "quiz", "project")
IMPORTANCES = ("core", "optional")
COURSE_STATUSES = ("active", "finished", "abandoned")
PROGRESS = ("planned", "in progress", "done")
"""planned : no document yet. in progress : an exam waiting for answers or for its correction. done : a class saved, an exam corrected."""
CLASSES_PER_EXAM = 3
"""The skill asks for at least one exam every 3 classes."""
NEXT_STEPS = 3
"""The number of steps to come returned with the state of a course."""
ICONS = {"class": "📖 class", "quiz": "❓ quiz", "project": "🛠️ project", "planned": "⏳ planned", "in progress": "✍️ in progress", "done": "✅ done"}


# --------------------------------------------------------------------------- #
# Reading the plan
# --------------------------------------------------------------------------- #


def _legacy_plan(course: Document) -> list[dict]:
    """The plan of a course created before the plans : one step per document of its old "## Content" section."""
    steps = []
    for stem, alias in objects.legacy_content(course.body):
        kind = next((kind for kind in STEP_KINDS if stem.startswith(objects.step_prefix(kind))), None)
        if kind is None:
            continue
        step = {"slug": stem[len(objects.step_prefix(kind)):], "kind": kind, "title": alias or stem, "description": "", "skills": [], "importance": "core"}
        path = objects.step_file(objects.course_slug(course), step)
        if path.is_file():
            document = vault.read(path)
            step["title"] = str(document.metadata.get("title") or step["title"])
            step["description"] = str(document.metadata.get("summary") or "")
            step["skills"] = [objects.unlink(item.get("skill", "")) for item in document.metadata.get("skills") or [] if isinstance(item, dict)]
        steps.append(step)
    return steps


def course_plan(course: Document) -> list[dict]:
    """The steps of the plan of a course, in order. A course created before the plans gets one from its documents."""
    if "plan" not in course.metadata:
        return _legacy_plan(course)
    return [step for step in course.metadata.get("plan") or [] if isinstance(step, dict) and step.get("kind") in STEP_KINDS]


def progress(course: str, step: dict) -> str:
    path = objects.step_file(course, step)
    if not path.is_file():
        return "planned"
    if step["kind"] == "class":
        return "done"
    return "done" if vault.read(path).metadata.get("status") == "corrected" else "in progress"


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
    """The slugs taken in a folder ("classes" or "exams") : by a document of any course, or by a step of any plan."""
    taken = {objects.slug(path) for path in objects.courses_dir().glob(f"*/{folder}/*.md")}
    for course in objects.iter_courses():
        taken.update(step["slug"] for step in course_plan(course) if objects.STEP_FOLDERS[step["kind"]] == folder)
    return taken


def new_slug(kind: str, title: str, taken: Optional[set[str]] = None) -> str:
    """A slug for a new step, unique among the documents and the steps of every course. Adds it to `taken`."""
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


def add_unplanned(course: Document, kind: str, title: str, description: str, skills: list[str]) -> tuple[dict, str]:
    """Adds a document created outside the plan to the plan, after the last step started. Returns the step and a warning."""
    course_slug = objects.course_slug(course)
    steps = course_plan(course)
    step = {"slug": new_slug(kind, title), "kind": kind, "title": title, "description": description, "skills": skills, "importance": "optional", "added": True}
    started = [step["slug"] for step in steps if progress(course_slug, step) != "planned"]
    course.metadata["plan"] = insert(steps, [step], started[-1] if started else "")
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


# --------------------------------------------------------------------------- #
# The "## Plan" table
# --------------------------------------------------------------------------- #


def _cell(value) -> str:
    return " ".join(str(value if value is not None else "").replace("|", "\\|").split())


def _link(stem: str, title: str) -> str:
    """A link to a note that may not exist yet. Inside a table, the | of the alias must be escaped."""
    alias = " ".join(title.replace("|", "/").replace("[", "(").replace("]", ")").split())
    return f"[[{stem}\\|{alias}]]"


def render(course: Document) -> None:
    """Writes the plan of a course (migrating an old "## Content" section) as the "## Plan" table of its body. The caller must write the document."""
    slug = objects.course_slug(course)
    steps = course_plan(course)
    course.metadata["plan"] = steps
    lines = [objects.PLAN_HEADING, ""]
    if steps:
        lines += ["| # | Step | Type | Description | Skills | Importance | Progress |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for number, step in enumerate(steps, 1):
            importance = step["importance"] + (" · ➕ added" if step.get("added") else "")
            lines.append(
                f"| {number} | {_link(objects.step_prefix(step['kind']) + step['slug'], step['title'])} | {ICONS[step['kind']]} | "
                f"{_cell(step.get('description'))} | {_cell(', '.join(step['skills']))} | {importance} | {ICONS[progress(slug, step)]} |"
            )
    else:
        lines.append("Nothing planned yet.")
    table = "\n".join(lines)
    body = course.body
    bounds = objects.section(body, objects.PLAN_HEADING) or objects.section(body, objects.CONTENT_HEADING)
    if bounds is None:
        course.body = f"{table}\n\n{body.lstrip()}".rstrip() + "\n"
    else:
        start, end = bounds
        rest = body[end:].lstrip("\n")
        course.body = f"{body[:start]}{table}\n" + (f"\n{rest}" if rest else "")
