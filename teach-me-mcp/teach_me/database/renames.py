"""Notes renamed or moved in Obsidian, put back under the name and in the folder the tools expect.

The tools find every note by its file name (`skills/skill-<skill>.md`, ...), and the hidden data of an exam
by the name of its note. Obsidian lets the student rename or move any note : it then updates the links in
the other notes, but never the hidden data, so a renamed note would be lost to the tools.

Every note the tools write has an `id` property : its file name when it was created (`skill-convolution`,
`Home` for Home.md). At each start_session, `restore` looks for the notes whose name or folder doesn't
match their id, and puts them back :

- the note gets its name and its folder back. A course whose folder was renamed gets its folder back ;
- the links that Obsidian changed to the new name, in every note of the vault, point to the id again ;
- the name the student gave becomes an alias of the note (`aliases`), so that the quick switcher and the
  links still find the note by that name.

A note whose place is taken by another note with the same id is a copy (Obsidian's "Make a copy" keeps
the properties) : it stays where it is, with a warning. A note without an id (or with an id that doesn't
fit its type) gets its file name as id, when it is where the tools expect it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

HOME = "Home"
"""The id of Home.md."""
TOP_FOLDERS = {"user": "users", "project": "projects", "skill": "skills"}
COURSE_FOLDERS = {"class": "classes", "quiz": "exams", "exercise": "exams", "resource": "resources"}
"""The folder of each kind of note of a course, inside the folder of the course."""
PASSES = (("home", "user", "project", "skill", "course"), tuple(COURSE_FOLDERS))
"""The courses are put back first : the notes of a course are found through it."""


def _markdown_files() -> list[Path]:
    """The notes of the vault, outside the hidden folders (.teach-me, .obsidian, .trash, ...)."""
    root = vault.vault_path()
    return [path for path in sorted(root.rglob("*.md")) if not any(part.startswith(".") for part in path.relative_to(root).parts)]


def _notes(kinds: tuple[str, ...]) -> list[Document]:
    """The notes of these types, read quietly : a note that can't be read is reported by the tools that need it."""
    found = []
    for path in _markdown_files():
        try:
            document = vault.read(path)
        except (ToolError, OSError, UnicodeDecodeError):
            continue
        if document.metadata.get("type") in kinds:
            found.append(document)
    return found


def _course_of(document: Document) -> Optional[str]:
    """The course a note belongs to : the one its `course` property links to, or else the folder it is in."""
    candidates = [objects.unlink(value) for value in objects.as_list(document.metadata.get("course"))]
    courses = objects.courses_dir()
    if document.path.is_relative_to(courses) and len(document.path.relative_to(courses).parts) > 1:
        candidates.append(document.path.relative_to(courses).parts[0])
    return next((course for course in candidates if course and objects.course_file(course).is_file()), None)


def expected_path(document: Document, note_id: Optional[str] = None) -> Optional[Path]:
    """Where the tools look for a note with this id (its `id` property by default), or None when the id doesn't fit the type of the note."""
    kind = document.metadata.get("type")
    note_id = document.metadata.get("id") if note_id is None else note_id
    if not isinstance(note_id, str) or not note_id.strip() or re.search(r"[/\\\[\]|#^:]", note_id):
        return None
    root = vault.vault_path()
    if kind == "home":
        return root / f"{HOME}.md" if note_id == HOME else None
    prefix = objects.PREFIXES.get(kind)
    if prefix is None or not note_id.startswith(prefix) or note_id == prefix:
        return None
    if kind in TOP_FOLDERS:
        return root / TOP_FOLDERS[kind] / f"{note_id}.md"
    if kind == "course":
        return objects.course_file(note_id[len(prefix):])
    if kind in COURSE_FOLDERS:
        course = _course_of(document)
        return objects.courses_dir() / course / COURSE_FOLDERS[kind] / f"{note_id}.md" if course else None
    return None


def _same_file(path: Path, other: Path) -> bool:
    try:
        return os.path.samefile(path, other)
    except OSError:
        return False


def _rename(source: Path, target: Path) -> None:
    """Renames a file or a folder. A rename that only changes the case goes through a temporary name (Windows file systems ignore the case)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and _same_file(source, target):
        temporary = source.with_name(source.name + ".teach-me-rename")
        source.rename(temporary)
        source = temporary
    source.rename(target)


def _link_pattern(name: str) -> re.Pattern:
    """A wikilink or an embed to the note `name`, with or without a folder and the .md extension : [[name]], [[folder/name|alias]], ![[name#heading]]."""
    return re.compile(r"\[\[(?:[^\[\]|#\n]*/)?" + re.escape(name) + r"(?:\.md)?(?=\\?[|#\]])")


def relink(old: str, new: str) -> list[str]:
    """Makes the links to the note `old` point to the note `new`, in every note of the vault. Returns the paths of the notes changed.
    Nothing changes while a note named `old` exists : the links point to it."""
    files = _markdown_files()
    if old == new or any(path.stem == old for path in files):
        return []
    pattern, changed = _link_pattern(old), []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        replaced = pattern.sub(f"[[{new}", text)
        if replaced != text:
            vault.write_text(path, replaced)
            changed.append(vault.relative(path))
    return changed


def _put_back(document: Document, target: Path) -> str:
    """Moves a note to `target`, the folder of its course with it when the folder was renamed, then its links and its alias. Returns what changed."""
    path, courses = document.path, objects.courses_dir()
    before = vault.relative(path)
    folder_renamed = (
        document.metadata.get("type") == "course"
        and path.parent.parent == courses
        and path.parent.name != target.parent.name
        and (not target.parent.exists() or _same_file(path.parent, target.parent))
    )
    if folder_renamed:
        _rename(path.parent, target.parent)
        path = target.parent / path.name
    if path != target:
        _rename(path, target)
    change = f"{before} → {vault.relative(target)}"
    if document.path.stem != target.stem:
        relinked = relink(document.path.stem, target.stem)
        restored = vault.read(target)
        aliases = objects.as_list(restored.metadata.get("aliases"))
        if document.path.stem not in aliases:
            restored.metadata["aliases"] = [*aliases, document.path.stem]
            vault.write(restored)
        change += f" (the name '{document.path.stem}' kept as an alias" + (f", links fixed in {len(relinked)} note(s))" if relinked else ")")
    return change


def restore() -> list[str]:
    """Puts back the notes renamed or moved in Obsidian, and gives an id to the notes that lost theirs. Returns one line per note changed ;
    a note that can't be put back (its place is taken) is reported with a warning."""
    changes = []
    for kinds in PASSES:
        for found in _notes(kinds):
            try:
                document = vault.read(found.path)  # read again : putting back an earlier note may have changed its links, or its folder
            except (ToolError, OSError):
                continue
            target = expected_path(document)
            if target is None:  # no id yet, or one that doesn't fit : the note is known by its name, when it is where the tools expect it
                if expected_path(document, document.path.stem) == document.path:
                    document.metadata = {"id": document.path.stem, **{key: value for key, value in document.metadata.items() if key != "id"}}
                    vault.write(document)
                    changes.append(f"{vault.relative(document.path)} : id")
                continue
            if document.path == target:
                continue
            if target.exists() and not _same_file(document.path, target):
                vault.warn(
                    f"{vault.relative(document.path)} has the id of {vault.relative(target)} : it is probably a copy made in Obsidian, and the tools may count it twice. "
                    "Ask the student whether they want to keep it : if so, remove its `id` and `type` properties so that the tools leave it alone ; otherwise delete it."
                )
                continue
            changes.append(_put_back(document, target))
    return changes
