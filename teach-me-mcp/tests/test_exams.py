import json

import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import correct_exam, create_exam, get_course_state, grade_questions, read_exam, save_class, submit_answers

SINGLE = {
    "kind": "single",
    "text": "Which operation flips the kernel ?",
    "skills": ["convolution"],
    "options": ["Convolution", "Cross-correlation"],
    "correct_options": ["A"],
}
MULTIPLE = {
    "kind": "multiple",
    "text": "Which kernels are neutral elements ?",
    "skills": ["convolution"],
    "options": ["1x1 kernel with a 1", "3x3 kernel with a centered 1", "2x2 kernel with a 1", "Kernel full of ones"],
    "correct_options": ["A", "B"],
}
OPEN = {
    "kind": "open",
    "text": "Design a CNN for 64x64 pictures of cats and dogs.",
    "skills": ["cnn-architecture"],
    "expected_answer": "Convolutions + pooling, then a dense layer with 2 outputs.",
}
GRADES = [
    {"question": 1, "explanation": "Because."},
    {"question": 2, "explanation": "Both are neutral."},
    {"question": 3, "grade": "B", "explanation": "Pooling was missing."},
]


def _create(course, questions=(SINGLE, MULTIPLE, OPEN), title="Convolution quiz", **kwargs):
    return create_exam(course, title, list(questions), **kwargs)


def _grades(user):
    """The grade, score and history of each skill, without the details of the evaluations."""
    return {skill: {key: grade[key] for key in ("grade", "score", "history")} for skill, grade in objects.skill_grades(user).items()}


def _fill(vault, path, old, new):
    file = vault / path
    file.write_text(file.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")


def _correct(slug, answers, grades=GRADES, **kwargs):
    submit_answers(slug, answers)
    grade_questions(slug, grades)
    return correct_exam(slug, **kwargs)


def test_create_exam_renders_the_questions_and_hides_the_solutions(course, vault):
    exam = _create(course, intro="A quick check.", planned="convolution-quiz")
    assert exam == {"slug": "convolution-quiz", "path": "courses/computer-vision/exams/quiz-convolution-quiz.md", "questions": 3, "warnings": []}
    document = vault_io.read(vault / exam["path"])
    assert document.metadata["status"] == "assigned"
    assert document.metadata["type"] == "quiz" and document.metadata["course"] == "[[course-computer-vision]]"
    assert document.metadata["skills"] == ["[[skill-convolution]]", "[[skill-cnn-architecture]]"]  # flat : Obsidian's property panel and Bases read it
    assert document.metadata["questions"] == 3 and document.metadata["mean"] is None
    data = objects.exam_data("convolution-quiz")  # what the tools need, hidden from Obsidian
    assert data["questions"][0] == {"kind": "single", "skills": ["convolution"], "options": ["Convolution", "Cross-correlation"]}
    assert "## ❓ Question 1 · Single choice\n*Skill : [[skill-convolution|convolution]]*" in document.body
    assert "- [ ] **B.** Cross-correlation" in document.body
    assert "## ❓ Question 3 · Open question" in document.body and "**Your answer :**" in document.body
    assert "Pooling" not in document.body and "correct_options" not in json.dumps(document.metadata)  # no solution in the exam
    solutions = json.loads((vault / ".teach-me" / "solutions" / "convolution-quiz.json").read_text(encoding="utf-8"))
    assert solutions == [["A"], ["A", "B"], OPEN["expected_answer"]]
    state = get_course_state(course)
    assert state["pending_exams"][0]["slug"] == "convolution-quiz"
    assert document.metadata["order"] == 2 and document.metadata["started_at"]
    assert "convolution-quiz" not in [step["slug"] for step in state["plan"]["next_steps"]]  # in progress : in pending_exams


def test_exam_slugs_are_unique(course, vault):
    _create(course, planned="convolution-quiz")
    again = _create(course, [OPEN])
    assert again["slug"] == "convolution-quiz-2" and again["path"].endswith("/exams/quiz-convolution-quiz-2.md")
    assert objects.exam_data(again["slug"])["type"] == "quiz"


@pytest.mark.parametrize(
    "question, message",
    [
        ({**SINGLE, "skills": ["backpropagation"]}, "isn't declared in the course"),
        ({**SINGLE, "skills": []}, "associated with no skills"),
        ({**SINGLE, "kind": "oral"}, "unknown kind"),
        ({**SINGLE, "correct_options": ["A", "B"]}, "exactly one option"),
        ({**SINGLE, "correct_options": ["E"]}, "unknown options E"),
        ({**SINGLE, "options": ["Only one"]}, "2 to 8"),
        ({**OPEN, "expected_answer": ""}, "expected_answer"),
        ({**OPEN, "options": ["A", "B"]}, "can't have `options`"),
    ],
)
def test_invalid_questions(course, question, message):
    with pytest.raises(ToolError, match=message):
        _create(course, [question])


def test_answers_written_in_the_file(course, vault):
    exam = _create(course)
    _fill(vault, exam["path"], "- [ ] **A.** Convolution", "- [x] **A.** Convolution")
    _fill(vault, exam["path"], "- [ ] **A.** 1x1", "- [x] **A.** 1x1")
    _fill(vault, exam["path"], "**Your answer :**", "**Your answer :**\n\nTwo convolutions and a dense layer.")
    read = read_exam(exam["slug"])
    assert read["status"] == "filled"
    assert read["answers"] == [["A"], ["A"], "Two convolutions and a dense layer."]
    assert read["solutions"][1] == ["A", "B"]
    assert read["proposed_grades"] == ["A", "B", None]  # F1 of {A} against {A, B} : 2/3

    graded = grade_questions(exam["slug"], GRADES)
    assert graded == {"graded": [{"question": 1, "grade": "A"}, {"question": 2, "grade": "B"}, {"question": 3, "grade": "B"}], "ungraded": []}
    result = correct_exam(exam["slug"], comments={"convolution": "Forgot one neutral kernel"})
    assert result["grades"] == ["A", "B", "B"]
    assert result["skills"] == {"convolution": {"grade": "A", "score": 4.5}, "cnn-architecture": {"grade": "B", "score": 4.0}}
    assert result["mean"] == 4.33 and result["shares"]["B"] == 0.67

    document = vault_io.read(vault / exam["path"])
    assert document.metadata["status"] == "corrected"
    assert document.metadata["mean"] == 4.33
    data = objects.exam_data(exam["slug"])
    assert data["skills"]["convolution"] == {"grade": "A", "score": 4.5, "comment": "Forgot one neutral kernel"}
    assert [q["grade"] for q in data["questions"]] == result["grades"]
    body = document.body
    assert "| [[skill-convolution\\|convolution]] | A | 4.5/5 | Forgot one neutral kernel |" in body
    skill = objects.get_skill("convolution")
    assert {key: skill.metadata[key] for key in ("grade", "score", "evaluations", "progression")} == {"grade": "A", "score": 4.5, "evaluations": 1, "progression": "A"}
    assert skill.metadata["last_evaluated"] is not None
    assert f"[[quiz-{exam['slug']}\\|Convolution quiz]] | [[course-computer-vision\\|Computer vision]] | A | 4.5/5 | Forgot one neutral kernel |" in skill.body
    assert body.index("## ❓ Question 1") < body.index("## ✅ Correction")  # the exam is kept, the correction comes after
    assert "Two convolutions and a dense layer." in body and "Pooling was missing." in body
    assert "> [!Tip] Question 2 : B · The answer solves the main problems" in body and "**Solution :** A, B" in body
    state = get_course_state(course)
    assert {s["slug"]: s["grade"] for s in state["skills"]} == {"convolution": "A", "cnn-architecture": "B"}
    assert "corrected : 1 A, 2 B (mean 4.33/5)" in state["sessions"][0]["entries"]


def test_answers_given_in_the_chat(course, vault):
    exam = _create(course)
    submitted = submit_answers(exam["slug"], ["b", "A, B", "Some convolutions."])
    assert submitted["status"] == "filled" and submitted["proposed_grades"] == ["D", "A", None]
    body = vault_io.read(vault / exam["path"]).body
    assert "- [x] **B.** Cross-correlation" in body and "- [ ] **A.** Convolution" in body
    assert "- [x] **A.** 1x1" in body and "- [x] **B.** 3x3" in body and "Some convolutions." in body
    grade_questions(exam["slug"], [*GRADES[:2], {**GRADES[2], "grade": "C"}])
    assert correct_exam(exam["slug"])["grades"] == ["D", "A", "C"]


def test_the_model_can_change_a_proposed_grade_but_not_an_e(course):
    exam = _create(course)
    submit_answers(exam["slug"], ["A", "", ""])
    graded = grade_questions(exam["slug"], [{**GRADES[0], "grade": "B"}, {**GRADES[1], "grade": "A"}, {**GRADES[2], "grade": "A"}])
    assert [item["grade"] for item in graded["graded"]] == ["B", "E", "E"]  # unanswered : always E


def test_a_question_counts_for_each_of_its_skills(course):
    both = {**OPEN, "skills": ["convolution", "cnn-architecture"]}
    exam = _create(course, [SINGLE, both])
    result = _correct(exam["slug"], ["A", "Dense layers only."], [GRADES[0], {"question": 2, "grade": "D", "explanation": "No convolution."}])
    assert result["skills"] == {"convolution": {"grade": "B", "score": 3.0}, "cnn-architecture": {"grade": "D", "score": 1.0}}


def test_questions_are_graded_before_the_correction(course, vault):
    first, second = {**OPEN, "text": "First"}, {**OPEN, "text": "Second"}
    slug = _create(course, [first, second])["slug"]
    with pytest.raises(ToolError, match="no answer yet.*submit_answers"):
        grade_questions(slug, [{**GRADES[2], "question": 1}])
    submit_answers(slug, ["a", "b"])
    with pytest.raises(ToolError, match=r"question\(s\) 1, 2 have no grade"):
        correct_exam(slug)
    assert grade_questions(slug, [{**GRADES[2], "question": 1}])["ungraded"] == [2]
    grade_questions(slug, [{**GRADES[2], "question": 2, "grade": "D"}])
    assert grade_questions(slug, [{**GRADES[2], "question": 2, "grade": "A"}])["ungraded"] == []  # grading again replaces
    assert correct_exam(slug)["grades"] == ["B", "A"]
    assert not (vault / ".teach-me" / "grades" / f"{slug}.json").exists()  # a retake is graded again
    with pytest.raises(ToolError, match="have no grade"):
        correct_exam(slug)


def test_submitting_again_drops_the_grades(course):
    slug = _create(course, [OPEN])["slug"]
    submit_answers(slug, ["a"])
    grade_questions(slug, [{**GRADES[2], "question": 1}])
    submit_answers(slug, ["b"])
    assert read_exam(slug)["grades"] == []


def test_grades_check_their_arguments(course):
    slug = _create(course)["slug"]
    submit_answers(slug, ["A", "A", "text"])
    with pytest.raises(ToolError, match="from 1 to 3"):
        grade_questions(slug, [{**GRADES[0], "question": 4}])
    with pytest.raises(ToolError, match="has no `explanation`"):
        grade_questions(slug, [{**GRADES[0], "explanation": ""}])
    with pytest.raises(ToolError, match="needs a `grade`"):
        grade_questions(slug, [{"question": 3, "explanation": "No grade"}])
    with pytest.raises(ToolError, match="needs a `grade`"):
        grade_questions(slug, [{**GRADES[0], "grade": "F"}])


def test_answers_and_comments_are_checked(course):
    slug = _create(course)["slug"]
    with pytest.raises(ToolError, match="one answer per question"):
        submit_answers(slug, ["A"])
    with pytest.raises(ToolError, match="unknown options Z"):
        submit_answers(slug, ["Z", "A", "text"])
    with pytest.raises(ToolError, match="doesn't evaluate : nope"):
        _correct(slug, ["A", "A", "text"], comments={"nope": "?"})


def test_a_second_correction_never_removes_the_first_one(course, vault):
    exam = _create(course, [SINGLE])
    _correct(exam["slug"], ["B"], [{"question": 1, "explanation": "First correction"}])
    _correct(exam["slug"], ["A"], [{"question": 1, "explanation": "After the retake"}])
    body = vault_io.read(vault / exam["path"]).body
    assert body.count("## ✅ Correction (") == 2
    assert body.index("First correction") < body.index("After the retake")
    assert _grades("alice") == {"convolution": {"grade": "A", "score": 5.0, "history": ["A"]}}  # only the latest take counts


def test_progress_advice(course):
    assert get_course_state(course)["progress"]["advice"] == []
    for title in ("Convolution", "Kernels", "Padding"):
        save_class(course, title, "", "Content")
    progress = get_course_state(course)["progress"]
    assert progress["classes_since_last_exam"] == 3
    assert "propose an exercise" in progress["advice"][0]

    slug = _create(course, [SINGLE, MULTIPLE])["slug"]
    assert "waiting for an answer" in get_course_state(course)["progress"]["advice"][0]
    _correct(slug, ["B", "C"], GRADES[:2])
    progress = get_course_state(course)["progress"]
    assert progress["classes_since_last_exam"] == 0
    assert progress["last_corrected_exam"]["mean"] == 1.0
    assert "re-explain" in progress["advice"][0]


@pytest.mark.parametrize(
    "answers, advice",
    [(["A", "A, B"], "too easy"), (["A", "A, C"], "right"), (["A", "C"], "too hard")],
)
def test_difficulty_follows_the_mean(course, answers, advice):
    slug = _create(course, [SINGLE, MULTIPLE])["slug"]
    _correct(slug, answers, GRADES[:2])  # A A : 5 · A C : 3.5 · A D : 3
    assert advice in get_course_state(course)["progress"]["advice"][0]


def test_unknown_exam(course):
    with pytest.raises(ToolError, match="Unknown exam"):
        read_exam("nope")


def test_correct_exam_grades_in_one_call(course):
    slug = _create(course, planned="convolution-quiz")["slug"]
    submitted = submit_answers(slug, ["A", "A, B", "Convolutions then a dense layer."])
    assert "content" not in submitted  # the model just wrote it
    assert submitted["proposed_grades"] == ["A", "A", None] and submitted["solutions"][2] == OPEN["expected_answer"]
    result = correct_exam(slug, grades=GRADES, comments={"convolution": "Solid"})
    assert result["grades"] == ["A", "A", "B"]
    plan = get_course_state(course)["plan"]
    assert plan["done"] == 1 and plan["next_steps"][0]["slug"] == "convolution"  # the class of the plan is still to do


def test_correct_exam_completes_the_grades_given_before(course):
    slug = _create(course, [{**OPEN, "text": "First"}, {**OPEN, "text": "Second"}])["slug"]
    submit_answers(slug, ["a", "b"])
    grade_questions(slug, [{**GRADES[2], "question": 1}])  # a long quiz, graded in several steps
    with pytest.raises(ToolError, match=r"question\(s\) 2 have no grade"):
        correct_exam(slug, grades=[{**GRADES[2], "question": 1, "grade": "C"}])
    assert correct_exam(slug, grades=[{**GRADES[2], "question": 2, "grade": "A"}])["grades"] == ["C", "A"]


def test_planned_exam_must_match_its_step(course):
    with pytest.raises(ToolError, match="'first-cnn' is a deliverable, not a quiz"):
        _create(course, [OPEN], planned="first-cnn")
    with pytest.raises(ToolError, match="Unknown step 'nope'.*convolution-quiz \\(quiz\\)"):
        _create(course, planned="nope")
    exam = _create(course, [SINGLE], planned="convolution-quiz")
    assert exam["warnings"] == []
    with pytest.raises(ToolError, match="already has its document"):
        _create(course, [SINGLE], title="Again", planned="convolution-quiz")
