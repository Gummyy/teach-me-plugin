"""Migration 1 : from the notes of teach-me 0.2 to flat properties that Obsidian Bases can read.

Each step works on every note of the vault and returns one line per note it changed. The steps run in
order, each one on the notes as the previous steps left them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from teach_me.database import objects, vault
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


STEPS: list[Callable[[], list[str]]] = [add_types]


def run() -> list[str]:
    changes = []
    for step in STEPS:
        changes += step()
    return changes
