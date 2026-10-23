"""Creating, reading and correcting exams."""

import re
from typing import Literal, Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError

Outcome = Literal["correct", "incomplete", "wrong"]
_CORRECTION_HEADING = re.compile(r"\A\s*#{1,6}[^\n]*correction[^\n]*\n", re.IGNORECASE)


def create_exam(
    course: str,
    title: str,
    type: Literal["quiz", "project"],
    content: str,
    skills: list[str],
    project: Optional[str] = None,
) -> str:
    """Creates an exam with the status "assigned".

    Args:
        course (str): The slug of the course
        title (str): The title of the exam
        type (Literal["quiz", "project"]): The type of exam
        content (str): The exam, in markdown, with room for the answers of the student
        skills (list[str]): The names of the skills evaluated, which must be declared in the course
        project (Optional[str]): For a project exam, the slug of the project it builds towards. Defaults to None.

    Returns:
        str: The path of the exam file, relative to the vault, so the student can fill it
    """
    course_document = objects.get_course(course)
    if type not in objects.EXAM_TYPES:
        raise ToolError(f"Unknown exam type '{type}'. Use one of : {', '.join(objects.EXAM_TYPES)}.")
    if not (title or "").strip():
        raise ToolError("The exam needs a non empty `title`.")
    if not (content or "").strip():
        raise ToolError("The exam `content` is empty : send the exam itself, in markdown.")
    declared = objects.declared_skills(course_document)
    if not skills:
        raise ToolError(f"List the evaluated skills in `skills`. Skills declared in this course : {', '.join(declared)}.")
    unknown = [skill for skill in skills if skill not in declared]
    if unknown:
        raise ToolError(
            f"These skills are not declared in the course '{course}' : {', '.join(unknown)}. "
            f"Declared skills : {', '.join(declared)}."
        )
    if project is not None:
        objects.get_project(project)

    path = objects.new_document_path(course, "exams", title)
    label = objects.current_session(course_document)
    moment = vault.format_time(vault.now())
    metadata = {"title": title.strip(), "type": type, "status": "assigned", "session": label}
    if project is not None:
        metadata["project"] = vault.link(project)
    metadata.update(
        {
            "created_at": moment,
            "updated_at": moment,
            "skills": [{"name": skill, "mark": None, "comment": None} for skill in dict.fromkeys(skills)],
        }
    )
    vault.write(Document(path, metadata, content))
    objects.append_to_session(course_document, f"Exam {vault.link(path.stem)} assigned : {title.strip()} ({type})")
    vault.write(course_document)
    return vault.relative(path)


def read_exam(exam: str) -> dict:
    """Reads an exam, including the answers the student wrote in the file, and sets its status to "filled".

    Args:
        exam (str): The slug of the exam

    Returns:
        dict: {"slug", "title", "type", "status", "skills", "path", "content"}
    """
    document = objects.find_document("exams", exam)
    if document.metadata.get("status") == "assigned":
        document.metadata["status"] = "filled"
        document.metadata["updated_at"] = vault.format_time(vault.now())
        vault.write(document)
    return {
        "slug": document.slug,
        "title": document.metadata.get("title"),
        "type": document.metadata.get("type"),
        "status": document.metadata.get("status"),
        "skills": [evaluation.get("name") for evaluation in document.metadata.get("skills") or []],
        "path": vault.relative(document.path),
        "content": document.body,
    }


def correct_exam(
    exam: str,
    correction: str,
    marks: dict[str, int],
    outcomes: list[Outcome],
    comments: Optional[dict[str, str]] = None,
) -> dict:
    """Saves the correction of an exam and sets its status to "corrected". The exam itself is never rewritten : the correction is added below it.

    Args:
        exam (str): The slug of the exam
        correction (str): The correction, in markdown. It is appended at the end of the exam file under a dated "Correction" heading, after the questions and the answers already in the file. Don't repeat the questions : for each question, give its number, the answer of the student when it isn't in the file (e.g. a quiz taken in the chat) and the correction.
        marks (dict[str, int]): A mark between 0 and 100 for each evaluated skill
        outcomes (list[Literal["correct", "incomplete", "wrong"]]): The outcome of each question, in order
        comments (Optional[dict[str, str]]): A short comment for each evaluated skill. Defaults to None.

    Returns:
        dict: {"correct": float, "incomplete": float, "wrong": float, "marks": dict} : the share of each outcome, to adjust the difficulty of the next exam
    """
    document = objects.find_document("exams", exam)
    evaluations = [evaluation for evaluation in document.metadata.get("skills") or [] if isinstance(evaluation, dict)]
    evaluated = [str(evaluation.get("name")) for evaluation in evaluations]
    comments = comments or {}

    if not (correction or "").strip():
        raise ToolError("The `correction` is empty : send the correction of each question, in markdown.")
    unknown = [skill for skill in [*marks, *comments] if skill not in evaluated]
    if unknown:
        raise ToolError(f"This exam doesn't evaluate : {', '.join(dict.fromkeys(unknown))}. Evaluated skills : {', '.join(evaluated)}.")
    missing = [skill for skill in evaluated if skill not in marks]
    if missing:
        raise ToolError(f"Give a mark to every evaluated skill. Missing : {', '.join(missing)}.")
    for skill, mark in marks.items():
        if isinstance(mark, bool) or not isinstance(mark, int) or not 0 <= mark <= 100:
            raise ToolError(f"The mark of '{skill}' must be an integer between 0 and 100, not {mark!r}.")
    if not outcomes:
        raise ToolError("Give the outcome of each question in `outcomes`.")
    invalid = [outcome for outcome in outcomes if outcome not in ("correct", "incomplete", "wrong")]
    if invalid:
        raise ToolError(f"Invalid outcomes : {', '.join(map(str, invalid))}. Use 'correct', 'incomplete' or 'wrong'.")

    for evaluation in evaluations:
        name = str(evaluation.get("name"))
        evaluation["mark"] = marks[name]
        evaluation["comment"] = comments.get(name, evaluation.get("comment"))
    document.metadata["status"] = "corrected"
    document.metadata["updated_at"] = vault.format_time(vault.now())
    correction = _CORRECTION_HEADING.sub("", correction, count=1).strip()  # the tool writes its own heading
    heading = f"## ✅ Correction ({vault.format_session(vault.now())})"
    document.body = f"{document.body.rstrip()}\n\n{heading}\n\n{correction}".lstrip("\n")
    vault.write(document)

    shares = {outcome: round(outcomes.count(outcome) / len(outcomes), 2) for outcome in ("correct", "incomplete", "wrong")}
    counts = ", ".join(f"{outcomes.count(outcome)} {outcome}" for outcome in ("correct", "incomplete", "wrong"))
    course_document = objects.get_course(objects.document_course(document))
    objects.append_to_session(course_document, f"Exam {vault.link(document.slug)} corrected : {counts}")
    vault.write(course_document)
    return {**shares, "marks": dict(marks)}
