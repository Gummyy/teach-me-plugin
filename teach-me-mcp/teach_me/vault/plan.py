"""`teach-vault plan` : the generated tables of the course notes, rebuilt from the properties of the notes.

A course note keeps its generated tables between Obsidian comments, which reading view hides :

    %% plan:start %% ... %% plan:end %%        every chosen step, half day by half day
    %% extras:start %% ... %% extras:end %%    the proposed activities, to pick from
    %% skills:start %% ... %% skills:end %%    every skill, where it is taught and where it is evaluated

A block missing from a course note is left out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from teach_me.vault.notes import EXAMS, ICONS, Note, Vault

HEADER = "| Day | Half day | Step | Type | Duration | Description | Skills | Status |\n| --- | --- | --- | --- | --- | --- | --- | --- |"
BLOCKS = ("plan", "extras", "skills")


def cell(value) -> str:
    """A table cell : no line break, and the `|` escaped."""
    text = "" if value is None else str(value)
    return re.sub(r"(?<!\\)\|", r"\\|", " ".join(text.split()))


def link(note: Note) -> str:
    return f"[[{note.stem}\\|{cell(note.title)}]]"


def skill_links(vault: Vault, step: Note) -> str:
    names = step.links_to("skills")
    return ", ".join(link(vault.notes[name]) if name in vault.notes else f"[[{name}]]" for name in names)


def row(vault: Vault, step: Note) -> str:
    cells = [
        cell(step.get("date") or step.get("day", "")),
        cell(step.get("half_day", "")),
        link(step),
        ICONS[step.type],
        cell(step.get("duration", "")),
        cell(step.get("description", "")),
        skill_links(vault, step),
        cell(step.status),
    ]
    return "| " + " | ".join(cells) + " |"


def table(vault: Vault, steps: list[Note]) -> str:
    return "\n".join([HEADER, *(row(vault, step) for step in steps)])


def coverage(vault: Vault, course: Note) -> dict[str, tuple[list[Note], list[Note]]]:
    """For every skill of the course : the chosen steps that teach it, and the chosen exams that evaluate it."""
    chosen = vault.steps(course, ("chosen",))
    result = {}
    for skill in vault.skills(course):
        uses = [step for step in chosen if skill.stem in step.links_to("skills")]
        result[skill.stem] = ([s for s in uses if s.type not in EXAMS], [s for s in uses if s.type in EXAMS])
    return result


def skills_table(vault: Vault, course: Note) -> str:
    short = lambda step: f"{link(step)} (day {step.get('day', '?')})"  # noqa: E731
    lines, section = [], object()
    for stem, (taught, evaluated) in coverage(vault, course).items():
        skill = vault.notes[stem]
        if skill.get("section") != section:
            section = skill.get("section")
            lines += ["", f"### {section}" if section else "### Skills", "", "| Skill | Taught in | Evaluated in |", "| --- | --- | --- |"]
        lines.append(f"| {link(skill)} | {', '.join(map(short, taught))} | {', '.join(map(short, evaluated)) or '⚠️ not evaluated'} |")
    return "\n".join(lines).strip("\n")


def render(vault: Vault, course: Note) -> dict[str, str]:
    return {
        "plan": table(vault, vault.steps(course, ("chosen",))),
        "extras": table(vault, vault.steps(course, ("proposed",))),
        "skills": skills_table(vault, course),
    }


def replace_block(text: str, name: str, content: str) -> tuple[str, bool]:
    """Replaces the content of a generated block. Returns the new text, and whether the block exists."""
    pattern = re.compile(rf"(^%% {name}:start %%[ \t]*\n).*?(^%% {name}:end %%)", re.DOTALL | re.MULTILINE)
    if not pattern.search(text):
        return text, False
    return pattern.sub(lambda m: m.group(1) + content + "\n" + m.group(2), text, count=1), True


@dataclass
class Result:
    course: Note
    new_text: str
    missing: list[str] = field(default_factory=list)
    """The blocks the course note doesn't have."""

    @property
    def changed(self) -> bool:
        return self.new_text != self.course.text


def rebuild(vault: Vault) -> list[Result]:
    """The course notes with their generated tables rebuilt. Writes nothing."""
    results = []
    for course in vault.courses():
        text, missing = course.text, []
        for name, content in render(vault, course).items():
            text, found = replace_block(text, name, content)
            if not found:
                missing.append(name)
        results.append(Result(course, text, missing))
    return results


def write(results: list[Result]) -> None:
    for result in results:
        if result.changed:
            result.course.path.write_text(result.new_text, encoding="utf-8", newline="\n")
