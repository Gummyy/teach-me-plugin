"""The views of the vault : Obsidian bases, embedded in the notes, that show the data of the notes without anyone updating them.

    bases/course.base     the views of a course, embedded in its note : `this` is the course note,
                          its folder holds the notes of its steps and resources, and it links to its skills and projects
    bases/project.base    the views of a project, embedded in its note : `this` is the project note,
                          the courses linking to it, and the skills of these courses
    bases/home.base       the views of Home.md, across the courses : exams to answer, last steps,
                          resources to look at, skills to work on, projects

A course note starts with a generated block embedding these views (see `blocks.py`), then the
student's "My notes" section, then the session log. A project note starts with its own block, then
its description, its progress log and the "My notes" section.

The bases are written when they are missing. A migration rewrites them when a new version changes them.
"""

from __future__ import annotations

from pathlib import Path

from teach_me.database import blocks, vault
from teach_me.database.vault import Document

COURSE_BLOCK = "dashboard"
STEP_TYPES = ("class", "quiz", "exercise")

_STEPS_FILTER = "\n".join(f"            - 'type == \"{kind}\"'" for kind in STEP_TYPES)

_IN_COURSE = "        - 'file.inFolder(this.file.folder)'"

COURSE_BASE = f"""# Written by teach-me : the views of a course, embedded in its note with ![[course.base#<view>]].
# `this` is the course note : its folder holds the notes of the course, and it links to its skills and projects.
formulas:
  step: 'file.asLink(title)'
  resource: 'file.asLink(title)'
  skill: 'file.asLink(name)'
  project: 'file.asLink(name)'
  where: 'if(url, url, file)'
  kind: 'if(type == "class", "📖 class", if(type == "quiz", "❓ quiz", "🛠️ project"))'
  progress: 'if(status == "done" || status == "corrected", "✅ done", if(status == "planned", "⏳ planned", "✍️ " + status))'
summaries:
  Evaluated: 'values.filter(value).mean().round(2)'
properties:
  note.order:
    displayName: "#"
  formula.step:
    displayName: Step
  formula.skill:
    displayName: Skill
  formula.kind:
    displayName: Type
  formula.resource:
    displayName: Resource
  formula.where:
    displayName: Link
  formula.project:
    displayName: Project
  note.step:
    displayName: Shared in
  note.status:
    displayName: Status
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
  note.grade:
    displayName: Grade
  note.score:
    displayName: Score
  note.progression:
    displayName: Progression
  note.last_evaluated:
    displayName: Last evaluated
  note.mean:
    displayName: Mean
views:
  - type: table
    name: Plan
    filters:
      and:
{_IN_COURSE}
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
{_IN_COURSE}
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
{_IN_COURSE}
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
  - type: table
    name: Skills
    filters:
      and:
        - 'type == "skill"'
        - 'this.file.hasLink(file)'
    sort:
      - property: file.name
        direction: ASC
    order:
      - formula.skill
      - description
      - grade
      - score
      - progression
      - last_evaluated
    summaries:
      score: Evaluated
  - type: table
    name: Exams
    filters:
      and:
{_IN_COURSE}
        - or:
            - 'type == "quiz"'
            - 'type == "exercise"'
        - 'status != "planned"'
        - 'status != "dropped"'
    sort:
      - property: started_at
        direction: ASC
    order:
      - started_at
      - formula.step
      - formula.kind
      - status
      - mean
    summaries:
      mean: Evaluated
  - type: list
    name: Projects
    filters:
      and:
        - 'type == "project"'
        - 'this.file.hasLink(file)'
    order:
      - formula.project
  - type: kanban
    name: Resources
    filters:
      and:
{_IN_COURSE}
        - 'type == "resource"'
    groupBy:
      property: note.status
      direction: ASC
    groupOrder:
      - new
      - seen
      - discussed
      - dropped
    order:
      - formula.resource
      - formula.where
      - step
"""

PROJECT_BASE = """# Written by teach-me : the views of a project, embedded in its note with ![[project.base#<view>]].
# `this` is the project note : its courses link to it, and their skills are found through the links to each skill.
# `file.backlinks` is computed when the note opens : a course linked to the project during the session shows on the next opening.
formulas:
  course: 'file.asLink(name)'
  skill: 'file.asLink(name)'
  courses: 'file.backlinks.filter(value.asFile().properties.type == "course" && value.asFile().hasLink(this.file))'
summaries:
  Evaluated: 'values.filter(value).mean().round(2)'
properties:
  formula.course:
    displayName: Course
  formula.skill:
    displayName: Skill
  formula.courses:
    displayName: Courses
  note.status:
    displayName: Status
  note.subject:
    displayName: Subject
  note.updated_at:
    displayName: Last activity
  note.description:
    displayName: Description
  note.grade:
    displayName: Grade
  note.score:
    displayName: Score
  note.progression:
    displayName: Progression
  note.last_evaluated:
    displayName: Last evaluated
views:
  - type: table
    name: Courses
    filters:
      and:
        - 'type == "course"'
        - 'file.hasLink(this.file)'
    sort:
      - property: updated_at
        direction: DESC
    order:
      - formula.course
      - status
      - subject
      - updated_at
  - type: table
    name: Skills
    filters:
      and:
        - 'type == "skill"'
        - 'file.backlinks.filter(value.asFile().properties.type == "course" && value.asFile().hasLink(this.file)).length > 0'
    sort:
      - property: file.name
        direction: ASC
    order:
      - formula.skill
      - description
      - formula.courses
      - grade
      - score
      - progression
      - last_evaluated
    summaries:
      score: Evaluated
"""

HOME_BASE = """# Written by teach-me : the views of Home.md, across all the courses of the vault.
formulas:
  name: 'if(title, file.asLink(title), file.asLink(name))'
properties:
  formula.name:
    displayName: Name
  note.course:
    displayName: Course
  note.status:
    displayName: Status
  note.started_at:
    displayName: Date
  note.updated_at:
    displayName: Last activity
  note.grade:
    displayName: Grade
  note.score:
    displayName: Score
  note.progression:
    displayName: Progression
views:
  - type: table
    name: Courses
    filters: 'type == "course"'
    sort:
      - property: updated_at
        direction: DESC
    order:
      - formula.name
      - status
      - updated_at
  - type: table
    name: Exams to answer
    filters:
      and:
        - or:
            - 'type == "quiz"'
            - 'type == "exercise"'
        - or:
            - 'status == "assigned"'
            - 'status == "filled"'
    sort:
      - property: started_at
        direction: ASC
    order:
      - formula.name
      - course
      - status
      - started_at
  - type: table
    name: Last steps
    limit: 5
    filters:
      and:
        - or:
            - 'type == "class"'
            - 'type == "quiz"'
            - 'type == "exercise"'
        - 'status != "planned"'
        - 'status != "dropped"'
    sort:
      - property: started_at
        direction: DESC
    order:
      - started_at
      - formula.name
      - course
      - status
  - type: table
    name: Resources to look at
    filters:
      and:
        - 'type == "resource"'
        - or:
            - 'status == "new"'
            - 'status == "seen"'
    order:
      - formula.name
      - course
      - status
  - type: table
    name: Skills to work on
    limit: 10
    filters:
      and:
        - 'type == "skill"'
        - 'evaluations > 0'
    sort:
      - property: score
        direction: ASC
    order:
      - formula.name
      - grade
      - score
      - progression
  - type: table
    name: Projects
    filters: 'type == "project"'
    sort:
      - property: updated_at
        direction: DESC
    order:
      - formula.name
      - updated_at
"""

BASES = {"course.base": COURSE_BASE, "project.base": PROJECT_BASE, "home.base": HOME_BASE}

COURSE_DASHBOARD = """## 📍 Where you are

Last steps :

![[course.base#Last steps]]

Next steps :

![[course.base#Next steps]]

## 🗺️ Plan

![[course.base#Plan]]

## 🎓 Report card

![[course.base#Skills]]

![[course.base#Exams]]

## 🛠️ Projects

![[course.base#Projects]]

## 📚 Resources

Drag a resource to *seen* once you had a look, and write what you thought of it in its note : your teacher will ask you about it.

![[course.base#Resources]]"""
"""The views at the top of a course note."""

PROJECT_BLOCK = "dashboard"
PROJECT_DASHBOARD = """## 📚 Courses

The courses that work on this project.

![[project.base#Courses]]

## 🎯 Skills

What these courses teach, and where you stand.

![[project.base#Skills]]"""
"""The views at the top of a project note."""

HOME_BLOCK = "home"
HOME_DASHBOARD = """# 🏠 Home

## Courses

![[home.base#Courses]]

## Exams to answer

![[home.base#Exams to answer]]

## Last steps

![[home.base#Last steps]]

## Resources to look at

![[home.base#Resources to look at]]

## Skills to work on

![[home.base#Skills to work on]]

## Projects

![[home.base#Projects]]"""
"""The views of Home.md, the entry point of the vault."""


def bases_dir() -> Path:
    return vault.vault_path() / "bases"


def ensure_bases(force: bool = False) -> list[str]:
    """Writes the bases that are missing (all of them with `force`). Returns their paths relative to the vault."""
    written = []
    for name, content in BASES.items():
        path = bases_dir() / name
        if path.is_file() and (not force or path.read_text(encoding="utf-8") == content):
            continue
        vault.write_text(path, content)
        written.append(vault.relative(path))
    return written


def home_file() -> Path:
    return vault.vault_path() / "Home.md"


def ensure_home() -> None:
    """Writes the bases and Home.md, the entry point of the vault, with its views written again if the student broke them."""
    ensure_bases()
    path = home_file()
    document = vault.read(path) if path.is_file() else Document(path, {"type": "home", "created_at": vault.format_time(vault.now())}, "")
    body = blocks.ensure_notes(blocks.replace(document.body, HOME_BLOCK, HOME_DASHBOARD, vault.format_session(vault.now()), first=True))
    if body != document.body or document.mtime_ns is None:
        document.body = body
        vault.write(document)


def render_course(course: Document) -> None:
    """Writes the views at the top of a course note, and its "My notes" section. The caller must write the document."""
    ensure_bases()
    body = blocks.replace(course.body, COURSE_BLOCK, COURSE_DASHBOARD, vault.format_session(vault.now()), first=True)
    course.body = blocks.ensure_notes(body)


def render_project(project: Document) -> None:
    """Writes the views at the top of a project note. The caller must write the document."""
    ensure_bases()
    project.body = blocks.replace(project.body, PROJECT_BLOCK, PROJECT_DASHBOARD, vault.format_session(vault.now()), first=True)
