"""A `teach-them` vault on disk : its notes, their properties and who may see them."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Optional

import yaml

from teach_me.vault import markdown

STEPS = ("class", "activity", "quiz", "autonomy", "deliverable", "presentation")
EXAMS = ("quiz", "deliverable", "presentation")
ICONS = {
    "class": "📖 class",
    "activity": "🤸 activity",
    "quiz": "❓ quiz",
    "autonomy": "🧭 autonomy",
    "deliverable": "📦 deliverable",
    "presentation": "🎤 presentation",
}
HALF_DAYS = {"morning": 0, "day": 1, "afternoon": 2}
TEACHER_FOLDER = "instructions"
IGNORED_FOLDERS = {".obsidian", ".git", ".trash"}


@dataclass
class Note:
    path: Path
    relative: str
    """Path relative to the vault, with forward slashes."""
    text: str
    properties: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    error: Optional[str] = None
    """Why the frontmatter couldn't be read, or None."""

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def type(self) -> str:
        return str(self.properties.get("type") or "")

    @property
    def status(self) -> str:
        return str(self.properties.get("status") or "")

    @cached_property
    def title(self) -> str:
        return markdown.title(self.body, self.stem)

    @property
    def teacher_only(self) -> bool:
        """The students never see this note : `audience: teacher`, an instructions note, or a note of an `instructions/` folder."""
        return (
            str(self.properties.get("audience") or "") == "teacher"
            or self.type == "instructions"
            or TEACHER_FOLDER in Path(self.relative).parts[:-1]
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def links_to(self, key: str) -> list[str]:
        """The note names of a property holding a link or a list of links."""
        value = self.properties.get(key)
        values = value if isinstance(value, list) else [value] if value else []
        return [markdown.unlink(item) for item in values if item]

    def day(self) -> int:
        try:
            return int(self.properties.get("day"))
        except (TypeError, ValueError):
            return 99

    def sort_key(self) -> tuple:
        try:
            order = int(self.properties.get("order"))
        except (TypeError, ValueError):
            order = 99
        return (self.day(), HALF_DAYS.get(str(self.properties.get("half_day")), 3), order, self.stem)


def read_note(path: Path, root: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    note = Note(path, path.relative_to(root).as_posix(), text)
    try:
        note.properties, note.body = markdown.parse_frontmatter(text)
    except yaml.YAMLError as error:
        note.body = markdown.split_frontmatter(text)[1]
        note.error = f"invalid YAML frontmatter ({str(error).splitlines()[0]})"
    return note


def files(root: Path) -> list[Path]:
    """Every file of the vault, outside the Obsidian, git and trash folders."""
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not IGNORED_FOLDERS.intersection(path.relative_to(root).parts)
    )


class Vault:
    def __init__(self, root: Path):
        self.root = root.resolve()
        all_files = files(self.root)
        self.notes: dict[str, Note] = {}
        self.duplicates: list[str] = []
        for path in all_files:
            if path.suffix != ".md":
                continue
            note = read_note(path, self.root)
            if note.stem in self.notes:
                self.duplicates.append(note.relative)
            else:
                self.notes[note.stem] = note
        self.attachments = {path.name for path in all_files if path.suffix != ".md"}

    def of_type(self, *types: str) -> list[Note]:
        return sorted((n for n in self.notes.values() if n.type in types), key=Note.sort_key)

    def courses(self) -> list[Note]:
        return self.of_type("course")

    def belongs(self, note: Note, course: Note) -> bool:
        """A note belongs to a course when its `course` property links to it, or when the vault has only that course."""
        linked = note.links_to("course")
        return course.stem in linked or (not linked and len(self.courses()) == 1)

    def steps(self, course: Note, statuses: tuple[str, ...] = ("chosen", "proposed")) -> list[Note]:
        return [n for n in self.of_type(*STEPS) if n.status in statuses and self.belongs(n, course)]

    def skills(self, course: Note) -> list[Note]:
        """The skills of a course : every skill note when the vault has one course, else the skills its steps use."""
        skills = self.of_type("skill")
        if len(self.courses()) == 1:
            used = skills
        else:
            names = {s for step in self.steps(course, ("chosen", "proposed", "dropped")) for s in step.links_to("skills")}
            used = [s for s in skills if s.stem in names]
        return sorted(used, key=lambda s: (str(s.get("section") or ""), s.stem))


def is_teach_them_vault(folder: Path) -> bool:
    """A folder holding `courses/` and a `type: course` note in it."""
    courses = folder / "courses"
    if not courses.is_dir():
        return False
    for path in courses.glob("*/*.md"):
        try:
            head = path.read_text(encoding="utf-8")
        except OSError:
            continue
        raw, _ = markdown.split_frontmatter(head)
        if raw is not None and any(line.strip() in ("type: course", 'type: "course"') for line in raw.splitlines()):
            return True
    return False


def find_vault(path: Path) -> Optional[Path]:
    """The `teach-them` vault holding a file, or None."""
    for folder in path.resolve().parents:
        if is_teach_them_vault(folder):
            return folder
    return None
