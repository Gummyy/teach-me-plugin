"""Structured exams : rendering the questions, reading the answers, grading, rendering the correction.

An exam file looks like this :

    # Title

    *How to answer*

    ## ❓ Question 1 · Single choice
    *Skill : [[skill-convolution|convolution]]*

    The question

    - [ ] **A.** First option
    - [x] **B.** Second option        <- ticked by the student

    ## ❓ Question 2 · Open question
    *Skills : [[skill-convolution|convolution]], [[skill-cnn-architecture|cnn-architecture]]*

    The question

    **Your answer :**

    The answer of the student

    ## ✅ Correction (2026-10-24 18:00)   <- appended by correct_exam, never rewritten

Only pure functions here : no file access.
"""

import re
import string
from typing import Optional

from teach_me.errors import ToolError

LETTERS = string.ascii_uppercase
KINDS = {"open": "Open question", "single": "Single choice", "multiple": "Multiple choices"}
GRADES = {
    "A": {"description": "The answer is correct and solves all the problems raised by the question", "value": 5},
    "B": {"description": "The answer solves the main problems raised by the question but misses some aspects", "value": 4},
    "C": {"description": "The answer is incomplete and doesn't solve the main problem raised by the question", "value": 2},
    "D": {"description": "The solution is wrong and doesn't answer the question", "value": 1},
    "E": {"description": "No answer was provided", "value": 0},
}
GRADE_THRESHOLDS = (("A", 4.5), ("B", 3), ("C", 1.5), ("D", 0.5))
"""A mean score gets the closest grade : the thresholds are halfway between the values of the grades."""
F1_THRESHOLDS = (("A", 1), ("B", 2 / 3), ("C", 1 / 3))
"""Grade proposed for a closed question from the F1-score of the ticked options : below the last threshold, D."""
CALLOUTS = {"A": "Success", "B": "Tip", "C": "Warning", "D": "Failure", "E": "Failure"}
ANSWER_MARKER = "**Your answer :**"
MAX_OPTIONS = 8

_QUESTION_HEADING = re.compile(r"^## ❓ Question (\d+)\b.*$", re.MULTILINE)
_CORRECTION_HEADING = re.compile(r"^## ✅ Correction\b.*$", re.MULTILINE)
_OPTION = re.compile(r"^(\s*-\s*\[)([ xX])(\]\s*\*\*([A-Z])\.\*\*)", re.MULTILINE)


# --------------------------------------------------------------------------- #
# Questions
# --------------------------------------------------------------------------- #


def validate_questions(questions: list, declared_skills: list[str]) -> tuple[list[dict], list]:
    """Checks the questions sent by the model.

    Returns the public part of each question (stored in the exam) and the solutions (kept hidden).
    """
    if not questions:
        raise ToolError("An exam needs at least one question in `questions`.")
    public, solutions = [], []
    for number, question in enumerate(questions, start=1):
        where = f"Question {number}"
        if not isinstance(question, dict):
            raise ToolError(f"{where} must be an object with 'kind', 'text' and 'skills'.")
        kind = question.get("kind")
        if kind not in KINDS:
            raise ToolError(f"{where} : unknown kind '{kind}'. Use one of : {', '.join(KINDS)}.")
        text = str(question.get("text") or "").strip()
        if not text:
            raise ToolError(f"{where} has no `text`.")
        raw = question.get("skills") or []
        skills = list(dict.fromkeys(str(skill).strip() for skill in ([raw] if isinstance(raw, str) else raw) if str(skill).strip()))
        if not skills:
            raise ToolError(
                f"{where} is associated with no skills. Associate it with at least one skill among : {', '.join(declared_skills)}"
            )
        for skill in skills:
            if skill not in declared_skills:
                raise ToolError(f"{where} evaluates '{skill}', which isn't declared in the course. Declared skills : {', '.join(declared_skills)}.")

        if kind == "open":
            if question.get("options") or question.get("correct_options"):
                raise ToolError(f"{where} is an open question : it can't have `options` or `correct_options`.")
            expected = str(question.get("expected_answer") or "").strip()
            if not expected:
                raise ToolError(f"{where} is an open question : give its `expected_answer`, so that it can be corrected later.")
            public.append({"kind": kind, "skills": skills, "text": text})
            solutions.append(expected)
            continue

        options = [str(option).strip() for option in question.get("options") or []]
        if not 2 <= len(options) <= MAX_OPTIONS or not all(options):
            raise ToolError(f"{where} is a closed question : give 2 to {MAX_OPTIONS} non empty `options`.")
        letters = LETTERS[: len(options)]
        correct = normalize_letters(question.get("correct_options") or [], letters, f"{where} `correct_options`")
        if not correct:
            raise ToolError(f"{where} : give the letters of the correct options in `correct_options`, e.g. [\"B\"].")
        if kind == "single" and len(correct) != 1:
            raise ToolError(f"{where} is a single choice question : exactly one option must be correct, not {len(correct)}. Use the kind 'multiple' otherwise.")
        public.append({"kind": kind, "skills": skills, "text": text, "options": options})
        solutions.append(correct)
    return public, solutions


def normalize_letters(value, letters: str, where: str) -> list[str]:
    """'a, C' or ['A', 'c'] -> ['A', 'C']"""
    items = re.split(r"[\s,;]+", value) if isinstance(value, str) else list(value)
    result = sorted({str(item).strip().upper().rstrip(".") for item in items if str(item).strip()})
    invalid = [letter for letter in result if letter not in letters]
    if invalid:
        raise ToolError(f"{where} : unknown options {', '.join(invalid)}. Valid options : {', '.join(letters)}.")
    return result


# --------------------------------------------------------------------------- #
# Rendering the exam
# --------------------------------------------------------------------------- #


def render_exam(title: str, intro: str, questions: list[dict], skill_links: dict[str, str]) -> str:
    instructions = []
    if any(question["kind"] != "open" for question in questions):
        instructions.append("tick the box of each answer you choose : `- [x]` (single choice : one box, multiple choices : one or more)")
    if any(question["kind"] == "open" for question in questions):
        instructions.append("write each open answer on the lines below its \"Your answer\" line")
    parts = [f"# {title}"]
    if intro.strip():
        parts.append(intro.strip())
    parts.append(f"*To answer : {' ; '.join(instructions)}.*")
    for number, question in enumerate(questions, start=1):
        skills = ", ".join(skill_links[skill] for skill in question["skills"])
        label = "Skills" if len(question["skills"]) > 1 else "Skill"
        lines = [f"## ❓ Question {number} · {KINDS[question['kind']]}", f"*{label} : {skills}*", "", question["text"], ""]
        if question["kind"] == "open":
            lines += [ANSWER_MARKER, ""]
        else:
            lines += [f"- [ ] **{letter}.** {option}" for letter, option in zip(LETTERS, question["options"])]
        parts.append("\n".join(lines).rstrip())
    return "\n\n".join(parts) + "\n"


# --------------------------------------------------------------------------- #
# Answers
# --------------------------------------------------------------------------- #


def _split(body: str) -> tuple[str, dict[int, tuple[int, int]], str]:
    """Splits an exam body into : the text before the questions, the span of each question, and the correction part."""
    correction = _CORRECTION_HEADING.search(body)
    end = correction.start() if correction else len(body)
    headings = [match for match in _QUESTION_HEADING.finditer(body) if match.start() < end]
    spans = {}
    for index, match in enumerate(headings):
        stop = headings[index + 1].start() if index + 1 < len(headings) else end
        spans[int(match.group(1))] = (match.start(), stop)
    return body[: headings[0].start() if headings else end], spans, body[end:]


def parse_answers(body: str, questions: list[dict]) -> list[Optional[object]]:
    """Reads the answers written in the exam file : a list of letters for a closed question, a text for an open one, None when unanswered."""
    _, spans, _ = _split(body)
    answers: list[Optional[object]] = []
    for number, question in enumerate(questions, start=1):
        if number not in spans:
            answers.append(None)
            continue
        section = body[spans[number][0] : spans[number][1]]
        if question["kind"] == "open":
            _, marker, text = section.partition(ANSWER_MARKER)
            answers.append(text.strip() or None if marker else None)
        else:
            ticked = sorted(match.group(4) for match in _OPTION.finditer(section) if match.group(2) in "xX")
            answers.append(ticked or None)
    return answers


def normalize_answers(raw: list[str], questions: list[dict]) -> list[Optional[object]]:
    """Answers given in the chat : "B" or "A, C" for a closed question, the text for an open one, "" when unanswered."""
    if len(raw) != len(questions):
        raise ToolError(f"Give one answer per question in `answers` : {len(questions)} expected, {len(raw)} received. Use \"\" for an unanswered question.")
    answers: list[Optional[object]] = []
    for number, (answer, question) in enumerate(zip(raw, questions), start=1):
        text = str(answer or "").strip()
        if question["kind"] == "open":
            answers.append(text or None)
        else:
            letters = LETTERS[: len(question["options"])]
            answers.append(normalize_letters(text, letters, f"Answer to question {number}") or None)
    return answers


def write_answers(body: str, questions: list[dict], answers: list[Optional[object]]) -> str:
    """Writes answers given in the chat into the exam file, where the student would have written them."""
    _, spans, _ = _split(body)
    for number in sorted(spans, reverse=True):  # from the end, so that the spans stay valid
        if number > len(questions):
            continue
        question, answer = questions[number - 1], answers[number - 1]
        start, stop = spans[number]
        section = body[start:stop]
        if question["kind"] == "open":
            before, marker, _ = section.partition(ANSWER_MARKER)
            if marker:
                section = f"{before}{marker}\n\n{answer or ''}".rstrip() + "\n\n"
        else:
            chosen = set(answer or [])
            section = _OPTION.sub(lambda m: f"{m.group(1)}{'x' if m.group(4) in chosen else ' '}{m.group(3)}", section)
        body = body[:start] + section + body[stop:]
    return body


# --------------------------------------------------------------------------- #
# Grading and correction
# --------------------------------------------------------------------------- #


def grade_of(score: float) -> str:
    """The grade closest to a mean score, between 0 and 5."""
    return next((grade for grade, threshold in GRADE_THRESHOLDS if score >= threshold), "E")


def propose_closed(answer: Optional[list], solution: list) -> str:
    """Grade proposed for a closed question, from the F1-score of the ticked options against the correct ones. Nothing ticked : E."""
    chosen, correct = set(answer or []), set(solution)
    if not chosen:
        return "E"
    right = len(chosen & correct)
    f1 = 2 * right / (len(chosen) + len(correct))
    return next((grade for grade, threshold in F1_THRESHOLDS if f1 >= threshold - 1e-9), "D")


def mean_score(grades: list[str]) -> float:
    return round(sum(GRADES[grade]["value"] for grade in grades) / len(grades), 2)


def skill_grades(questions: list[dict], grades: list[str]) -> dict[str, dict]:
    """Grade of each skill in one exam : {"grade", "score"}, from the mean value of its questions.

    A question that evaluates several skills counts fully for each of them.
    """
    values: dict[str, list[str]] = {}
    for question, grade in zip(questions, grades):
        for skill in question["skills"]:
            values.setdefault(skill, []).append(grade)
    return {skill: {"grade": grade_of(mean_score(skill_values)), "score": mean_score(skill_values)} for skill, skill_values in values.items()}


def _format_answer(question: dict, answer) -> str:
    if answer is None:
        return "*no answer*"
    if question["kind"] == "open":
        return str(answer)
    return ", ".join(answer)


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.strip().splitlines())


def render_correction(label: str, questions: list[dict], answers: list, solutions: list, explanations: list[str], grades: list[str]) -> str:
    counts = ", ".join(f"**{grades.count(grade)}** {grade}" for grade in GRADES if grade in grades)
    parts = [f"## ✅ Correction ({label})", f"{counts} · mean **{mean_score(grades)}/5**"]
    for number, (question, answer, solution, explanation, grade) in enumerate(zip(questions, answers, solutions, explanations, grades), start=1):
        if question["kind"] == "open":
            details = f"**Your answer :**\n\n{_format_answer(question, answer)}\n\n**Expected :**\n\n{solution}"
        else:
            details = f"**Your answer :** {_format_answer(question, answer)} · **Solution :** {', '.join(solution)}"
        title = f"Question {number} : {grade} · {GRADES[grade]['description']}"
        parts.append(f"> [!{CALLOUTS[grade]}] {title}\n{_quote(details)}\n>\n{_quote(explanation)}")
    return "\n\n".join(parts)
