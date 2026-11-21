"""`teach-vault check` : what a `teach-them` vault must hold before the teacher uses it."""

from __future__ import annotations

import re
from collections import defaultdict

from teach_me.vault import markdown
from teach_me.vault.notes import EXAMS, Note, Vault
from teach_me.vault.plan import coverage

EXAM_SECTIONS = {
    "instructions for the students": "Instructions for the students",
    "expected outcome": "Expected outcome",
    "correction": "Correction",
    "tips": "Tips to guide the students",
}
"""The 4 sections of an exam : the start of their heading, and its full name for the messages."""
POSTPONED = re.compile(r"^>\s*\[!todo\]", re.IGNORECASE | re.MULTILINE)


def broken_links(vault: Vault) -> list[str]:
    """Every wikilink and heading anchor resolves, in the properties and the body (code is ignored)."""
    errors = []
    for note in vault.notes.values():
        for found in markdown.links(note.text):
            target = vault.notes.get(found.note) if found.note else note
            if target is None:
                if found.note not in vault.attachments:
                    errors.append(f"{note.relative}: {found.raw} → no such note")
                continue
            heading = (found.heading or "").split("#")[-1].strip()
            if heading and not heading.startswith("^") and heading not in markdown.headings(target.body):
                errors.append(f"{note.relative}: {found.raw} → no heading '{heading}' in {target.stem}")
    return errors


def teacher_links(vault: Vault) -> list[str]:
    """No student note links to a teacher note outside a teacher block."""
    errors = []
    for note in vault.notes.values():
        if note.teacher_only:
            continue
        spans = markdown.teacher_spans(note.body)
        for found in markdown.links(note.body):
            target = vault.notes.get(found.note)
            if target is None or not target.teacher_only:
                continue
            if not any(start <= found.start < end for start, end in spans):
                errors.append(f"{note.relative}: {found.raw} → {target.stem} is a teacher note : move the link into a %% teacher:start %% block")
    return errors


def unevaluated_skills(vault: Vault) -> list[str]:
    errors = []
    for course in vault.courses():
        for stem, (_, evaluated) in coverage(vault, course).items():
            if not evaluated:
                errors.append(f"{vault.notes[stem].relative}: evaluated by no chosen quiz, deliverable or presentation of {course.stem}")
    return errors


def missing_recalls(vault: Vault) -> list[str]:
    """Every day but the first and the last opens with a quiz, when the teacher is there that day.

    A deliverable handed in at the start of the day may come before the quiz.
    """
    errors = []
    for course in vault.courses():
        days: dict[int, list[Note]] = defaultdict(list)
        for step in vault.steps(course, ("chosen",)):
            if step.day() != 99:
                days[step.day()].append(step)
        if len(days) < 3:
            continue
        first, last = min(days), max(days)
        for day in sorted(days):
            with_teacher = [s for s in days[day] if s.type not in ("autonomy", "deliverable")]
            if first < day < last and with_teacher and with_teacher[0].type != "quiz":
                errors.append(f"{course.relative}: day {day} opens with {with_teacher[0].stem}, not with a recall quiz")
    return errors


def missing_sections(vault: Vault) -> list[str]:
    errors = []
    for exam in vault.of_type(*EXAMS):
        if exam.status == "dropped":
            continue
        found = [h.lower() for h in markdown.headings(exam.body)]
        missing = [name for start, name in EXAM_SECTIONS.items() if not any(h.startswith(start) for h in found)]
        if missing:
            errors.append(f"{exam.relative}: missing section(s) {', '.join(missing)}")
    return errors


def note_errors(vault: Vault) -> list[str]:
    errors = [f"{note.relative}: {note.error}" for note in vault.notes.values() if note.error]
    errors += [f"{path}: same file name as another note, Obsidian can't tell them apart" for path in vault.duplicates]
    if not vault.courses():
        errors.append("no note with `type: course` in the vault")
    return errors


def postponed(vault: Vault) -> list[str]:
    """The exams whose expected outcome or correction is still a `> [!todo]` : not a failure, listed for the review."""
    return [exam.relative for exam in vault.of_type(*EXAMS) if exam.status != "dropped" and POSTPONED.search(exam.body)]


def check(vault: Vault) -> list[str]:
    return note_errors(vault) + broken_links(vault) + teacher_links(vault) + unevaluated_skills(vault) + missing_recalls(vault) + missing_sections(vault)


def check_links(vault: Vault) -> list[str]:
    """The checks that make sense on a student vault, where the teacher parts are gone."""
    return [e for e in note_errors(vault) if "type: course" not in e] + broken_links(vault) + teacher_links(vault)
