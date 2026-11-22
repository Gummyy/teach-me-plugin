"""The views of the vault : Obsidian bases, embedded in the notes, that show the data of the notes without anyone updating them.

    bases/course.base     the views of a course, embedded in its note : `this` is the course note
                          and its folder holds the notes of its steps

A course note starts with a generated block embedding these views (see `blocks.py`), then the
student's "My notes" section, then the session log.

The bases are written when they are missing. A migration rewrites them when a new version changes them.
"""

from __future__ import annotations

from pathlib import Path

from teach_me.database import blocks, vault
from teach_me.database.vault import Document

COURSE_BLOCK = "dashboard"
STEP_TYPES = ("class", "quiz", "exercise")

_STEPS_FILTER = "\n".join(f"        - 'type == \"{kind}\"'" for kind in STEP_TYPES)

COURSE_BASE = f"""# Written by teach-me : the views of a course, embedded in its note with ![[course.base#<view>]].
# `this` is the course note, and its folder holds the notes of the course.
filters:
  and:
    - 'file.inFolder(this.file.folder)'
formulas:
  step: 'file.asLink(title)'
  kind: 'if(type == "class", "📖 class", if(type == "quiz", "❓ quiz", "🛠️ project"))'
  progress: 'if(status == "done" || status == "corrected", "✅ done", if(status == "planned", "⏳ planned", "✍️ " + status))'
properties:
  note.order:
    displayName: "#"
  formula.step:
    displayName: Step
  formula.kind:
    displayName: Type
  note.description:
    displayName: Description
  note.skills:
    displayName: Skills
  note.importance:
    displayName: Importance
  formula.progress:
    displayName: Progress
  note.started_at:
    displayName: Date
views:
  - type: table
    name: Plan
    filters:
      and:
        - or:
{_STEPS_FILTER}
        - 'status != "dropped"'
    sort:
      - property: order
        direction: ASC
    order:
      - order
      - formula.step
      - formula.kind
      - description
      - skills
      - importance
      - formula.progress
  - type: table
    name: Next steps
    limit: 3
    filters:
      and:
        - or:
{_STEPS_FILTER}
        - or:
            - 'status == "planned"'
            - 'status == "assigned"'
            - 'status == "filled"'
    sort:
      - property: order
        direction: ASC
    order:
      - order
      - formula.step
      - formula.kind
      - description
      - formula.progress
  - type: table
    name: Last steps
    limit: 3
    filters:
      and:
        - or:
{_STEPS_FILTER}
        - 'status != "planned"'
        - 'status != "dropped"'
    sort:
      - property: started_at
        direction: DESC
    order:
      - started_at
      - formula.step
      - formula.kind
      - formula.progress
"""

BASES = {"course.base": COURSE_BASE}

COURSE_DASHBOARD = """## 📍 Where you are

Last steps :

![[course.base#Last steps]]

Next steps :

![[course.base#Next steps]]

## 🗺️ Plan

![[course.base#Plan]]"""
"""The views at the top of a course note."""


def bases_dir() -> Path:
    return vault.vault_path() / "bases"


def ensure_bases(force: bool = False) -> list[str]:
    """Writes the bases that are missing (all of them with `force`). Returns their paths relative to the vault."""
    written = []
    for name, content in BASES.items():
        path = bases_dir() / name
        if path.is_file() and (not force or path.read_text(encoding="utf-8") == content):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(vault.relative(path))
    return written


def render_course(course: Document) -> None:
    """Writes the views at the top of a course note, and its "My notes" section. The caller must write the document."""
    ensure_bases()
    body = blocks.replace(course.body, COURSE_BLOCK, COURSE_DASHBOARD, vault.format_session(vault.now()), first=True)
    course.body = blocks.ensure_notes(body)
