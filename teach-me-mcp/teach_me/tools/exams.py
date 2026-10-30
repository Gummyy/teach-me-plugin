"""Creating, answering, grading and correcting exams.

An exam is a list of questions : open (the student writes the answer), single choice or multiple
choices. Each question evaluates one or more skills. The tools render the exam file, keep the
solutions hidden, propose a grade for the closed questions and compute the grade of each skill : the
model writes the questions, grades them (grade_questions) and explains them.

    create_exam -> (submit_answers, when the student answered in the chat) -> read_exam -> grade_questions -> correct_exam
"""

import json
from typing import Literal, Optional

from teach_me.database import objects, quiz, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.schemas import Question, QuestionGrade


def _solutions_file(exam: str):
    """The solutions are kept out of the exam file, in a hidden folder that Obsidian doesn't show."""
    return vault.vault_path() / ".teach-me" / "solutions" / f"{exam}.json"


def _grades_file(exam: str):
    """The grades of the questions, hidden until correct_exam appends the correction."""
    return vault.vault_path() / ".teach-me" / "grades" / f"{exam}.json"


def _read_grades(exam: str) -> dict[int, dict]:
    file = _grades_file(exam)
    if not file.is_file():
        return {}
    return {int(number): grade for number, grade in json.loads(file.read_text(encoding="utf-8")).items()}


def _read_solutions(exam: str) -> list:
    file = _solutions_file(exam)
    if not file.is_file():
        raise ToolError(f"The solutions of the exam '{exam}' are missing ({vault.relative(file)}) : it can't be graded.")
    return json.loads(file.read_text(encoding="utf-8"))


def _question_number(value, questions: list[dict], where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= len(questions):
        raise ToolError(f"{where} : `question` must be the number of a question, from 1 to {len(questions)}, not {value!r}.")
    return value


def _questions(document: Document) -> list[dict]:
    questions = document.metadata.get("questions")
    if not questions:
        raise ToolError(f"The exam '{objects.slug(document)}' was created by an older version of teach-me, without structured questions : it can't be read or corrected with this tool.")
    return questions


def _stored(question: dict) -> dict:
    """What the exam's frontmatter keeps of a question : enough to read and grade the answers. The text is in the body."""
    return {key: question[key] for key in ("kind", "skills", "options") if key in question}


def _proposals(questions: list[dict], answers: list, solutions: list) -> list[Optional[str]]:
    """Grade proposed for each question : from the F1-score for a closed question, E for an unanswered one, None for an answered open question."""
    proposals = []
    for question, answer, solution in zip(questions, answers, solutions):
        if answer is None:
            proposals.append("E")
        elif question["kind"] == "open":
            proposals.append(None)
        else:
            proposals.append(quiz.propose_closed(answer, solution))
    return proposals


def _set_status(document: Document, status: str) -> None:
    document.metadata["status"] = status
    document.metadata["updated_at"] = vault.format_time(vault.now())


def create_exam(
    course: str,
    title: str,
    type: Literal["quiz", "project"],
    questions: list[Question],
    intro: Optional[str] = None,
    project: Optional[str] = None,
) -> dict:
    """Creates an exam with the status "assigned" and writes it in the vault, ready to be answered. It is added to the content of the course.

    The tool numbers the questions, labels the options A, B, C, ... and keeps the solutions hidden from the student.

    Args:
        course (str): The slug of the course
        title (str): The title of the exam
        type (Literal["quiz", "project"]): "quiz" for a quick check of knowledge, "project" for a practical exercise on the student's project (usually open questions). The questions of a project exam weigh twice as much in the grades of the skills.
        questions (list[Question]): The questions, in order. Each evaluates one or more skills of the course, given by their slugs
        intro (Optional[str]): A short context shown before the questions, in markdown. Defaults to None.
        project (Optional[str]): For a project exam, the slug of the project it builds towards. Defaults to None.

    Returns:
        dict: {"slug", "path", "questions"} : the slug of the exam, its path relative to the vault, and the number of questions
    """
    course_document = objects.get_course(course)
    if type not in objects.EXAM_TYPES:
        raise ToolError(f"Unknown exam type '{type}'. Use one of : {', '.join(objects.EXAM_TYPES)}.")
    if not (title or "").strip():
        raise ToolError("The exam needs a non empty `title`.")
    title = title.strip()
    public, solutions = quiz.validate_questions(questions, objects.course_skills(course_document))
    skills = list(dict.fromkeys(skill for question in public for skill in question["skills"]))
    skill_links = {
        skill: objects.link("skill", skill, objects.skill_file(skill), alias=objects.get_skill(skill).metadata.get("name") or skill)
        for skill in skills
    }

    path = objects.new_document_path(course, "exams", title, exam_type=type)
    exam = objects.slug(path)
    label = objects.current_session(course_document)
    moment = vault.format_time(vault.now())
    metadata = {"title": title, "type": type, "status": "assigned", "session": label}
    if project is not None:
        metadata["project"] = objects.link("project", project, objects.project_file(project))
    metadata.update(
        {
            "created_at": moment,
            "updated_at": moment,
            "skills": [{"skill": skill_links[skill], "grade": None, "score": None, "comment": None} for skill in skills],
            "questions": [_stored(question) for question in public],
        }
    )
    vault.write(Document(path, metadata, quiz.render_exam(title, intro or "", public, skill_links)))

    solutions_file = _solutions_file(exam)
    solutions_file.parent.mkdir(parents=True, exist_ok=True)
    solutions_file.write_text(json.dumps(solutions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    exam_link = objects.link("exam", exam, path, alias=title)
    objects.add_to_content(course_document, f"{'Quiz' if type == 'quiz' else 'Exercise'} : {exam_link}")
    objects.append_to_session(course_document, f"Exam {exam_link} assigned ({type}, {len(public)} questions)")
    vault.write(course_document)
    return {"slug": exam, "path": vault.relative(path), "questions": len(public)}


def submit_answers(exam: str, answers: list[str]) -> dict:
    """Writes the answers the student gave in the chat into the exam file, and sets its status to "filled". Skip it when the student answered in the file. Submitting again replaces the answers and the grades given so far.

    Args:
        exam (str): The slug of the exam
        answers (list[str]): One answer per question : "B" or "A, C" for a closed question, the text for an open one, "" when unanswered

    Returns:
        dict: {"slug", "status", "answers", "proposed_grades"} : the answers as recorded, and the grade proposed for each question (see read_exam)
    """
    document = objects.find_document("exams", exam)
    questions = _questions(document)
    given = quiz.normalize_answers(answers, questions)
    document.body = quiz.write_answers(document.body, questions, given)
    _set_status(document, "filled")
    vault.write(document)
    _grades_file(exam).unlink(missing_ok=True)  # graded on other answers
    return {"slug": exam, "status": "filled", "answers": given, "proposed_grades": _proposals(questions, given, _read_solutions(exam))}


def read_exam(exam: str) -> dict:
    """Reads an exam and the answers of the student. Sets its status to "filled" when the file contains answers.

    Args:
        exam (str): The slug of the exam

    Returns:
        dict: {"slug", "title", "type", "status", "path", "content", "answers", "solutions", "proposed_grades", "grades"} :
            the content of the exam file,
            the answers (letters for closed questions, text for open ones, null when unanswered),
            the solutions, for you only : don't show them before the student has answered,
            the grade proposed for each question : from the F1-score of the ticked options for a closed question, E for an unanswered question (it can't be changed), null for an open question (yours to grade),
            the grades given so far with grade_questions : [{"question", "grade"}]
    """
    document = objects.find_document("exams", exam)
    questions = _questions(document)
    answers = quiz.parse_answers(document.body, questions)
    if document.metadata.get("status") == "assigned" and any(answer is not None for answer in answers):
        _set_status(document, "filled")
        vault.write(document)
    solutions_file = _solutions_file(exam)
    solutions = json.loads(solutions_file.read_text(encoding="utf-8")) if solutions_file.is_file() else None
    return {
        "slug": exam,
        "title": document.metadata.get("title"),
        "type": document.metadata.get("type"),
        "status": document.metadata.get("status"),
        "path": vault.relative(document.path),
        "content": document.body,
        "answers": answers,
        "solutions": solutions,
        "proposed_grades": _proposals(questions, answers, solutions) if solutions is not None else None,
        "grades": [{"question": number, "grade": grade["grade"]} for number, grade in sorted(_read_grades(exam).items())],
    }


def grade_questions(exam: str, grades: list[QuestionGrade]) -> dict:
    """Grades questions of an exam, before correct_exam. Can be called several times, e.g. to grade a long project exam question by question : grading a question again replaces its grade. The grades stay hidden until correct_exam.

    Every question needs an explanation. Open questions need a grade. Closed questions take the grade proposed by read_exam when you leave it out, but you can change it (e.g. B instead of A when the question was trivial for the options ticked). An unanswered question always gets E.

    Args:
        exam (str): The slug of the exam
        grades (list[QuestionGrade]): The grades of some or all of the questions

    Returns:
        dict: {"graded", "ungraded"} : the questions graded so far ([{"question", "grade"}]), and the numbers of the ones still to grade before correct_exam
    """
    document = objects.find_document("exams", exam)
    questions = _questions(document)
    if not grades:
        raise ToolError("Give at least one grade in `grades`.")
    answers = quiz.parse_answers(document.body, questions)
    if all(answer is None for answer in answers):
        raise ToolError("The exam has no answer yet. If the student answered in the chat, call submit_answers first.")
    proposals = _proposals(questions, answers, _read_solutions(exam))
    stored = _read_grades(exam)
    for item in grades:
        number = _question_number((item or {}).get("question"), questions, "A grade")
        explanation = str(item.get("explanation") or "").strip()
        if not explanation:
            raise ToolError(f"The grade of question {number} has no `explanation`.")
        grade = item.get("grade")
        if proposals[number - 1] == "E":
            grade = "E"  # unanswered
        elif grade is None and questions[number - 1]["kind"] != "open":
            grade = proposals[number - 1]
        if grade not in quiz.GRADES:
            raise ToolError(f"Question {number} needs a `grade` among : {', '.join(quiz.GRADES)}.")
        stored[number] = {"grade": grade, "explanation": explanation}

    file = _grades_file(exam)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({str(n): stored[n] for n in sorted(stored)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {
        "graded": [{"question": number, "grade": stored[number]["grade"]} for number in sorted(stored)],
        "ungraded": [number for number in range(1, len(questions) + 1) if number not in stored],
    }


def correct_exam(exam: str, comments: Optional[dict[str, str]] = None) -> dict:
    """Corrects an exam once every question is graded (grade_questions) : computes the grade of each skill and appends the correction to the exam file. The exam itself is never rewritten.

    Args:
        exam (str): The slug of the exam
        comments (Optional[dict[str, str]]): A short comment for each evaluated skill, by slug. Defaults to None.

    Returns:
        dict: {"grades", "shares", "mean", "skills"} : the grade of each question, the share of each grade, the mean value of the exam (out of 5, to adjust the difficulty of the next exam) and the grade of each skill in this exam ({"grade", "score"}). A question counts for every skill it evaluates.
    """
    document = objects.find_document("exams", exam)
    questions = _questions(document)
    solutions = _read_solutions(exam)
    stored = _read_grades(exam)
    ungraded = [number for number in range(1, len(questions) + 1) if number not in stored]
    if ungraded:
        raise ToolError(f"Grade the question(s) {', '.join(map(str, ungraded))} with grade_questions first.")
    answers = quiz.parse_answers(document.body, questions)
    grades = [stored[number]["grade"] for number in range(1, len(questions) + 1)]
    explanations = [stored[number]["explanation"] for number in range(1, len(questions) + 1)]

    skills = quiz.skill_grades(questions, grades)
    comments = comments or {}
    unknown = [skill for skill in comments if skill not in skills]
    if unknown:
        raise ToolError(f"This exam doesn't evaluate : {', '.join(unknown)}. Evaluated skills : {', '.join(skills)}.")

    for evaluation in document.metadata.get("skills") or []:
        skill = objects.unlink(evaluation.get("skill", ""))
        evaluation.update(skills.get(skill, {}))
        evaluation["comment"] = comments.get(skill, evaluation.get("comment"))
    for question, grade in zip(questions, grades):
        question.pop("outcome", None)
        question["grade"] = grade
    _set_status(document, "corrected")
    correction_text = quiz.render_correction(vault.format_session(vault.now()), questions, answers, solutions, explanations, grades)
    document.body = f"{document.body.rstrip()}\n\n{correction_text}"
    vault.write(document)
    _grades_file(exam).unlink(missing_ok=True)  # a retake is graded again

    mean = quiz.mean_score(grades)
    counts = ", ".join(f"{grades.count(grade)} {grade}" for grade in quiz.GRADES if grade in grades)
    course_document = objects.get_course(objects.document_course(document))
    objects.append_to_session(course_document, f"Exam {objects.link('exam', exam, document.path)} corrected : {counts} (mean {mean}/5)")
    vault.write(course_document)
    return {
        "grades": grades,
        "shares": {grade: round(grades.count(grade) / len(grades), 2) for grade in quiz.GRADES},
        "mean": mean,
        "skills": skills,
    }
