"""Migration 1 : from the notes of teach-me 0.2 to flat properties that Obsidian Bases can read.

Each step works on every note of the vault and returns one line per note it changed. The steps run in
order, each one on the notes as the previous steps left them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from teach_me.database import dashboards, objects, quiz, vault
from teach_me.database import plan as plans
from teach_me.database.vault import Document

CONTENT_HEADING = "## Content"
"""The section that listed the classes and exams of a course before the plans (teach-me 0.1)."""
PLAN_HEADING = "## Plan"
"""The section that showed the plan of a course as a table (teach-me 0.2)."""


def _front(metadata: dict, first: dict) -> dict:
    """The properties of `first` first, then the others in their order."""
    return {**first, **{key: value for key, value in metadata.items() if key not in first}}


def _notes(folder: Path, pattern: str) -> list[Document]:
    return [vault.read(path) for path in sorted(folder.glob(pattern))]


def add_types() -> list[str]:
    """Every note gets its `type`, and the classes and exams the `course` they belong to. A project exam is an `exercise`."""
    changed = []

    def update(document: Document, first: dict) -> None:
        metadata = _front(document.metadata, first)
        if metadata != document.metadata or list(metadata) != list(document.metadata):
            document.metadata = metadata
            vault.write(document)
            changed.append(f"{vault.relative(document.path)} : type {first['type']}")

    for kind, folder in (("user", objects.users_dir()), ("project", objects.projects_dir()), ("skill", objects.skills_dir())):
        for document in _notes(folder, f"{objects.PREFIXES[kind]}*.md"):
            update(document, {"type": kind})
    for course in objects.iter_courses():
        slug = objects.course_slug(course)
        update(course, {"type": "course"})
        link = objects.course_link(slug)
        for document in _notes(objects.courses_dir() / slug / "classes", "*.md"):
            update(document, {"type": "class", "course": link})
        for document in _notes(objects.courses_dir() / slug / "exams", "*.md"):
            update(document, {"type": objects.EXAM_NOTE_TYPES[objects.exam_type(document)], "course": link})
    return changed


def flatten_exams() -> list[str]:
    """The questions and the grades of the skills of an exam move to its hidden data : the note keeps the links to its skills, the number of questions and the mean."""
    changed = []
    for course in objects.iter_courses():
        for exam in objects.iter_exams(objects.course_slug(course)):
            metadata = exam.metadata
            if not isinstance(metadata.get("questions"), list) and not any(isinstance(item, dict) for item in metadata.get("skills") or []):
                continue
            slug = objects.slug(exam)
            questions = [question for question in metadata.get("questions") or [] if isinstance(question, dict)]
            for question in questions:
                question.pop("outcome", None)
            evaluations = {}
            links = []
            for item in metadata.get("skills") or []:
                skill = objects.unlink(item.get("skill", "") if isinstance(item, dict) else item)
                links.append(f"[[{objects.PREFIXES['skill']}{skill}]]")
                if isinstance(item, dict) and item.get("grade"):
                    evaluations[skill] = {key: item.get(key) for key in ("grade", "score", "comment")}
            data = {"questions": questions, "skills": evaluations}
            grades = [question.get("grade") for question in questions if question.get("grade") in quiz.GRADES]
            if metadata.get("status") == "corrected":
                data["corrected_at"] = metadata.get("updated_at")
            if questions or evaluations:
                objects.write_exam_data(slug, data)
            metadata["skills"] = links
            metadata["questions"] = len(questions)
            metadata["mean"] = quiz.mean_score(grades) if metadata.get("status") == "corrected" and grades else None
            vault.write(exam)
            changed.append(f"{vault.relative(exam.path)} : questions and grades moved to .teach-me/exams/{slug}.json")
    return changed


def skill_notes() -> list[str]:
    """The description of a skill moves to its properties, and its note shows its grade and its history."""
    changed = []
    for document in _notes(objects.skills_dir(), f"{objects.PREFIXES['skill']}*.md"):
        if "description" in document.metadata:
            continue
        description = document.body.strip()
        document.metadata = _front(document.metadata, {"type": "skill", "name": document.metadata.get("name"), "description": description})
        document.body = objects.skill_body("", [])
        vault.write(document)
        changed.append(f"{vault.relative(document.path)} : description moved to the properties")
    for user in objects.iter_users():
        for skill in objects.refresh_skills(objects.slug(user)):
            changed.append(f"{vault.relative(objects.skill_file(skill))} : grade and history")
    return changed


def _section(body: str, heading: str) -> Optional[tuple[int, int]]:
    """Start and end of a "## " section of a body, heading included, or None."""
    match = re.search(rf"^{re.escape(heading)}[ \t]*$", body, re.MULTILINE)
    if match is None:
        return None
    following = re.search(r"^## ", body[match.end():], re.MULTILINE)
    return match.start(), match.end() + following.start() if following else len(body)


def _legacy_plan(course: Document) -> list[dict]:
    """The plan of a course created before the plans : one step per note linked in its "## Content" section."""
    bounds = _section(course.body, CONTENT_HEADING)
    if bounds is None:
        return []
    links = re.findall(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]", course.body[bounds[0]:bounds[1]])
    steps = []
    for stem, alias in dict.fromkeys((stem.strip(), alias.strip() or None) for stem, alias in links):
        kind = next((kind for kind in plans.STEP_KINDS if stem.startswith(objects.step_prefix(kind))), None)
        if kind is not None:
            steps.append({"slug": stem[len(objects.step_prefix(kind)):], "kind": kind, "title": alias or stem, "description": "", "skills": [], "importance": "core"})
    return steps


def plan_notes() -> list[str]:
    """Each step of the plan of a course becomes a note of its own, and the course note shows the plan with a base instead of a table."""
    changed = []
    for course in objects.iter_courses():
        slug = objects.course_slug(course)
        if "plan" in course.metadata:
            steps = [dict(step) for step in course.metadata.get("plan") or [] if isinstance(step, dict) and step.get("kind") in plans.STEP_KINDS]
        else:
            steps = _legacy_plan(course)
        known = {objects.step_file(slug, step) for step in steps}
        for folder, kinds in (("classes", ("class",)), ("exams", ("quiz", "project"))):
            for path in sorted((objects.courses_dir() / slug / folder).glob("*.md")):
                document = vault.read(path)
                if path in known or document.metadata.get("order") is not None:
                    continue
                kind = "class" if folder == "classes" else objects.exam_type(document)
                steps.append({"slug": objects.slug(path), "kind": kind, "title": str(document.metadata.get("title") or path.stem), "description": "", "skills": [], "importance": "optional", "added": True})
        for step in steps:
            path = objects.step_file(slug, step)
            if not path.is_file():
                continue
            document = vault.read(path)
            metadata = document.metadata
            summary = metadata.pop("summary", None)
            if summary and not step.get("description"):
                step["description"] = summary
            if metadata.get("title"):
                step["title"] = str(metadata["title"])
            if step["kind"] != "class" and metadata.get("skills"):
                step["skills"] = [objects.unlink(skill) for skill in metadata["skills"]]
            metadata.setdefault("status", "done" if step["kind"] == "class" else "assigned")
            metadata.setdefault("started_at", metadata.get("created_at"))
            vault.write(document)
        plans.write_plan(slug, steps)
        course = objects.get_course(slug)
        course.metadata.pop("plan", None)
        for heading in (PLAN_HEADING, CONTENT_HEADING):
            bounds = _section(course.body, heading)
            if bounds is not None:
                course.body = (course.body[:bounds[0]] + course.body[bounds[1]:]).strip("\n")
        dashboards.render_course(course)
        vault.write(course)
        changed.append(f"{vault.relative(course.path)} : {len(steps)} steps of the plan, each in its own note")
    return changed


STEPS: list[Callable[[], list[str]]] = [add_types, flatten_exams, skill_notes, plan_notes]


def run() -> list[str]:
    changes = []
    for step in STEPS:
        changes += step()
    return changes
