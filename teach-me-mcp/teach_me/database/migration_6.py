"""Migration 6 : the project exams give way to the deliverables.

- A project exam already given (it has questions : assigned, filled or corrected) becomes a quiz : `exercise-<slug>.md`
  is renamed `quiz-<slug>.md`, its questions stay as they are, and it now weighs as a quiz in the grades of the skills.
- A project exam only planned (or dropped) becomes a deliverable step : `deliverable-<slug>.md`, its planned body says so.
- The links to these notes, in every note of the vault, follow the new names.
- The bases are written again (the deliverables in the course, the project and Home.md), so are the views of the
  course notes, the project notes and Home.md, and every value deduced from the hidden data of the exams.
"""

from __future__ import annotations

from teach_me.database import dashboards, migration_2, migration_5, objects, renames, vault
from teach_me.database import plan as plans


def _move(document, kind: str) -> str:
    """Renames the note of a project exam to the prefix of `kind`, with its `type` and `id`, and makes the links follow."""
    slug = objects.slug(document)
    target = document.path.with_name(f"{objects.EXAM_PREFIXES[kind]}{slug}.md")
    if target.exists():
        vault.warn(f"{vault.relative(document.path)} can't become {vault.relative(target)} : a note already has that name. Ask the student which one to keep.")
        return ""
    old = document.path.stem
    metadata = {key: value for key, value in document.metadata.items() if key != "id"}
    metadata["type"] = objects.EXAM_NOTE_TYPES[kind]
    document.metadata = {"id": target.stem, **metadata}
    if kind == "deliverable" and document.body.strip() == plans.placeholder(objects.LEGACY).strip():
        document.body = plans.placeholder("deliverable")
    vault.write(document)
    renames._rename(document.path, target)
    relinked = renames.relink(old, target.stem)
    return f"{vault.relative(document.path)} → {vault.relative(target)}" + (f" (links fixed in {len(relinked)} note(s))" if relinked else "")


def exercises() -> list[str]:
    changed = []
    for path in sorted(objects.courses_dir().glob(f"*/exams/{objects.PREFIXES['exercise']}*.md")):
        for document in vault.read_all([path]):
            slug = objects.slug(document)
            data = objects.exam_data(slug, strict=False)
            if data.get("questions"):
                if data.get("type") != "quiz":
                    objects.write_exam_data(slug, {**data, "type": "quiz"})
                change = _move(document, "quiz")
            else:
                change = _move(document, "deliverable")
            if change:
                changed.append(change)
    return changed


def project_views() -> list[str]:
    changed = []
    for document in objects.iter_projects(None):
        before = document.body
        dashboards.render_project(document)
        if document.body != before:
            vault.write(document)
            changed.append(f"{vault.relative(document.path)} : views")
    return changed


def derived() -> list[str]:
    return [change for user in objects.iter_users() for change in objects.refresh_derived(objects.slug(user))]


def run() -> list[str]:
    return exercises() + migration_2.views() + migration_5.course_views() + project_views() + derived()
