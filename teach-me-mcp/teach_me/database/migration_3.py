"""Migration 3 : the hidden data of an exam is its source of truth.

The data of each exam given (`.teach-me/exams/<exam>.json`) gets the type of the exam, read until now from
its note. Then every value the tools deduce from that data is written again in the notes : the status,
mean, questions and skills of the exams, the grades and histories of the skills.
"""

from __future__ import annotations

from teach_me.database import objects, vault


def exam_types() -> list[str]:
    changed = []
    for path in sorted(objects.courses_dir().glob("*/exams/*.md")):
        for document in vault.read_all([path]):
            exam = objects.slug(document)
            data = objects.exam_data(exam, strict=False)
            if data.get("questions") and data.get("type") not in objects.EXAM_TYPES:
                objects.write_exam_data(exam, {"type": objects.note_exam_type(document), **data})
                changed.append(f"{vault.relative(objects.exam_data_file(exam))} : type")
    return changed


def derived() -> list[str]:
    return [change for user in objects.iter_users() for change in objects.refresh_derived(objects.slug(user))]


def run() -> list[str]:
    return exam_types() + derived()
