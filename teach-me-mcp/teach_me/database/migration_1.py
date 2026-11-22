"""Migration 1 : from the notes of teach-me 0.2 to flat properties that Obsidian Bases can read.

Each step works on every note of the vault and returns one line per note it changed. The steps run in
order, each one on the notes as the previous steps left them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from teach_me.database import objects, quiz, vault
from teach_me.database.vault import Document


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


STEPS: list[Callable[[], list[str]]] = [add_types, flatten_exams, skill_notes]


def run() -> list[str]:
    changes = []
    for step in STEPS:
        changes += step()
    return changes
