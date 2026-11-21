"""`teach-vault export` : the student version of a `teach-them` vault."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from teach_me.vault import markdown
from teach_me.vault.notes import Vault, files


class ExportError(Exception):
    pass


@dataclass
class Exported:
    copied: int
    left_out: int
    unlinked: int


def unlink_removed(text: str, removed: set[str]) -> tuple[str, int]:
    """Turns the links to removed notes into plain text : their alias, else the note name."""
    pieces, last, count = [], 0, 0
    for found in markdown.links(text):
        if found.note not in removed:
            continue
        pieces += [text[last : found.start], found.alias or found.note]
        last = found.start + len(found.raw)
        count += 1
    return "".join(pieces) + text[last:], count


def export(source: Path, destination: Path, force: bool = False) -> Exported:
    """Copies the vault without the teacher notes, the teacher blocks and the Obsidian workspace.

    Raises:
        ExportError: when the destination is inside the vault, or exists without `force`
    """
    vault = Vault(source)
    destination = destination.resolve()
    if destination == vault.root or vault.root in destination.parents:
        raise ExportError("The destination must be outside the teacher's vault.")
    if destination.exists():
        if not force:
            raise ExportError(f"{destination} exists. Use --force to replace it.")
        shutil.rmtree(destination)

    teacher = {note.path for note in vault.notes.values() if note.teacher_only}
    removed = {path.stem for path in teacher}
    copied = unlinked = 0
    obsidian = vault.root / ".obsidian"
    keep = [p for p in sorted(obsidian.rglob("*")) if p.is_file() and "workspace" not in p.name] if obsidian.is_dir() else []
    for path in files(vault.root) + keep:
        if path in teacher:
            continue
        target = destination / path.relative_to(vault.root)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            text, count = unlink_removed(markdown.remove_teacher_blocks(path.read_text(encoding="utf-8")), removed)
            target.write_text(text, encoding="utf-8", newline="\n")
            unlinked += count
        else:
            shutil.copy2(path, target)
        copied += 1
    return Exported(copied, len(teacher), unlinked)
