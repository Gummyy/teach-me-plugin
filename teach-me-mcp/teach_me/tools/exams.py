"""Creating, reading and correcting exams.

An exam is a list of questions : open (the student writes the answer), single choice or multiple
choices. The tools render the exam file, keep the solutions hidden, grade the closed questions and
compute the mark of each skill : the model only writes the questions, the explanations and the
outcome of the open questions.
"""

import json
from typing import Literal, Optional

from teach_me.database import objects, quiz, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.schemas import Question, QuestionCorrection


def _solutions_file(exam: str):
    """The solutions are kept out of the exam file, in a hidden folder that Obsidian doesn't show."""
    return vault.vault_path() / ".teach-me" / "solutions" / f"{exam}.json"


def _questions(document: Document) -> list[dict]:
    questions = document.metadata.get("questions")
    if not questions:
        raise ToolError(f"The exam '{document.slug}' was created by an older version of teach-me, without structured questions : it can't be read or corrected with this tool.")
    return questions


def _stored(question: dict) -> dict:
    """What the exam's frontmatter keeps of a question : enough to read and grade the answers. The text is in the body."""
    return {key: question[key] for key in ("kind", "skill", "options") if key in question}


def create_exam(
    course: str,
    title: str,
    type: Literal["quiz", "project"],
    questions: list[Question],
    intro: Optional[str] = None,
    project: Optional[str] = None,
) -> dict:
    """Creates an exam with the status "assigned" and writes it in the vault, ready to be answered.

    The tool numbers the questions, labels the options A, B, C, ... and keeps the solutions hidden from the student.

    Args:
        course (str): The slug of the course
        title (str): The title of the exam
        type (Literal["quiz", "project"]): "quiz" for a quick check of knowledge, "project" for a practical exercise on the student's project (usually open questions)
        questions (list[Question]): The questions, in order. Each evaluates one skill declared in the course
        intro (Optional[str]): A short context shown before the questions, in markdown. Defaults to None.
        project (Optional[str]): For a project exam, the slug of the project it builds towards. Defaults to None.

    Returns:
        dict: {"slug", "path", "questions"} : the slug of the exam, its path relative to the vault, and the questions as numbered in the file (without the solutions)
    """
    course_document = objects.get_course(course)
    if type not in objects.EXAM_TYPES:
        raise ToolError(f"Unknown exam type '{type}'. Use one of : {', '.join(objects.EXAM_TYPES)}.")
    if not (title or "").strip():
        raise ToolError("The exam needs a non empty `title`.")
    public, solutions = quiz.validate_questions(questions, objects.declared_skills(course_document))
    if project is not None:
        objects.get_project(project)

    path = objects.new_document_path(course, "exams", title)
    label = objects.current_session(course_document)
    moment = vault.format_time(vault.now())
    metadata = {"title": title.strip(), "type": type, "status": "assigned", "session": label}
    if project is not None:
        metadata["project"] = vault.link(project)
    skills = list(dict.fromkeys(skill for question in public for skill in question["skills"]))
    metadata.update(
        {
            "created_at": moment,
            "updated_at": moment,
            "skills": [{"name": skill, "mark": None, "comment": None} for skill in skills],
            "questions": [_stored(question) for question in public],
        }
    )
    vault.write(Document(path, metadata, quiz.render_exam(title.strip(), intro or "", public)))

    solutions_file = _solutions_file(path.stem)
    solutions_file.parent.mkdir(parents=True, exist_ok=True)
    solutions_file.write_text(json.dumps(solutions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    objects.append_to_session(course_document, f"Exam {vault.link(path.stem)} assigned : {title.strip()} ({type}, {len(public)} questions)")
    vault.write(course_document)
    return {"slug": path.stem, "path": vault.relative(path), "questions": len(public)}


def read_exam(exam: str) -> dict:
    """Reads an exam and the answers the student wrote in its file. Sets its status to "filled" when the file contains answers.

    Args:
        exam (str): The slug of the exam

    Returns:
        dict: {"slug", "title", "type", "status", "path", "content", "answers", "solutions"} : the content of the exam file, the answers read in it (letters for closed questions, text for open ones, null when unanswered) and the solutions, for you only : don't show them before the student has answered
    """
    document = objects.find_document("exams", exam)
    questions = _questions(document)
    answers = quiz.parse_answers(document.body, questions)
    if document.metadata.get("status") == "assigned" and any(answer is not None for answer in answers):
        document.metadata["status"] = "filled"
        document.metadata["updated_at"] = vault.format_time(vault.now())
        vault.write(document)
    solutions_file = _solutions_file(exam)
    solutions = json.loads(solutions_file.read_text(encoding="utf-8")) if solutions_file.is_file() else None
    return {
        "slug": document.slug,
        "title": document.metadata.get("title"),
        "type": document.metadata.get("type"),
        "status": document.metadata.get("status"),
        "path": vault.relative(document.path),
        "content": document.body,
        "answers": answers,
        "solutions": solutions,
    }


def correct_exam(
    exam: str,
    corrections: list[QuestionCorrection],
    answers: Optional[list[str]] = None,
    comments: Optional[dict[str, str]] = None,
) -> dict:
    """Corrects an exam : grades it, computes the mark of each skill and appends the correction to the exam file. The exam itself is never rewritten.

    The closed questions are graded by the tool from the student's answers. You give the outcome of the open questions only.

    Args:
        exam (str): The slug of the exam
        corrections (list[QuestionCorrection]): One correction per question, in order : an explanation for each, and the outcome of each open question
        answers (Optional[list[str]]): The student's answers, one per question, when they answered in the chat : "B" or "A, C" for a closed question, the text for an open one, "" when unanswered. They are written into the exam file. Leave it out when the student answered in the file. Defaults to None.
        comments (Optional[dict[str, str]]): A short comment for each evaluated skill. Defaults to None.

    Returns:
        dict: {"outcomes", "correct", "incomplete", "wrong", "marks"} : the outcome of each question, the share of each outcome (to adjust the difficulty of the next exam) and the mark of each skill
    """
    document = objects.find_document("exams", exam)
    questions = _questions(document)
    solutions_file = _solutions_file(exam)
    if not solutions_file.is_file():
        raise ToolError(f"The solutions of the exam '{exam}' are missing ({vault.relative(solutions_file)}) : it can't be graded.")
    solutions = json.loads(solutions_file.read_text(encoding="utf-8"))

    if len(corrections) != len(questions):
        raise ToolError(f"Give one correction per question in `corrections` : {len(questions)} expected, {len(corrections)} received.")
    if answers is not None:
        given = quiz.normalize_answers(answers, questions)
        document.body = quiz.write_answers(document.body, questions, given)
    else:
        given = quiz.parse_answers(document.body, questions)
        if all(answer is None for answer in given):
            raise ToolError("No answer found in the exam file. If the student answered in the chat, give their answers in `answers`.")

    outcomes, explanations = [], []
    for number, (question, answer, solution, correction) in enumerate(zip(questions, given, solutions, corrections), start=1):
        explanation = str((correction or {}).get("explanation") or "").strip()
        if not explanation:
            raise ToolError(f"The correction of question {number} has no `explanation`.")
        if question["kind"] == "open":
            outcome = (correction or {}).get("outcome")
            if outcome not in quiz.SCORES:
                raise ToolError(f"Question {number} is an open question : give its `outcome` ('correct', 'incomplete' or 'wrong').")
        else:
            outcome = quiz.grade_closed(answer, solution)
        outcomes.append(outcome)
        explanations.append(explanation)

    marks = quiz.skill_marks(questions, outcomes)
    comments = comments or {}
    unknown = [skill for skill in comments if skill not in marks]
    if unknown:
        raise ToolError(f"This exam doesn't evaluate : {', '.join(unknown)}. Evaluated skills : {', '.join(marks)}.")

    for evaluation in document.metadata.get("skills") or []:
        name = str(evaluation.get("name"))
        evaluation["mark"] = marks.get(name, evaluation.get("mark"))
        evaluation["comment"] = comments.get(name, evaluation.get("comment"))
    for question, outcome in zip(questions, outcomes):
        question["outcome"] = outcome
    document.metadata["status"] = "corrected"
    document.metadata["updated_at"] = vault.format_time(vault.now())
    correction_text = quiz.render_correction(vault.format_session(vault.now()), questions, given, solutions, explanations, outcomes)
    document.body = f"{document.body.rstrip()}\n\n{correction_text}"
    vault.write(document)

    shares = {outcome: round(outcomes.count(outcome) / len(outcomes), 2) for outcome in quiz.SCORES}
    counts = ", ".join(f"{outcomes.count(outcome)} {outcome}" for outcome in quiz.SCORES)
    course_document = objects.get_course(objects.document_course(document))
    objects.append_to_session(course_document, f"Exam {vault.link(document.slug)} corrected : {counts}")
    vault.write(course_document)
    return {"outcomes": outcomes, **shares, "marks": marks}
