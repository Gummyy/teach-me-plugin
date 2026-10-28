import json

import pytest

from teach_me.database import objects
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import correct_exam, create_exam, get_course_state, grade_open_questions, read_exam, save_class

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
EXPLAIN = [{"question": 1, "explanation": "Because."}, {"question": 2, "explanation": "Both are neutral."}]
GRADE = {"question": 3, "outcome": "incomplete", "explanation": "Pooling was missing."}


def _create(course, questions=(SINGLE, MULTIPLE, OPEN), **kwargs):
    return create_exam(course, "Convolution quiz", "quiz", list(questions), **kwargs)


def _fill(vault, path, old, new):
    file = vault / path
    file.write_text(file.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")


def test_create_exam_renders_the_questions_and_hides_the_solutions(course, vault):
    exam = _create(course, intro="A quick check.", project="pet-classifier")
    assert exam["questions"] == 3
    document = vault_io.read(vault / exam["path"])
    assert document.metadata["status"] == "assigned"
    assert document.metadata["project"] == "[[pet-classifier]]"
    assert document.metadata["skills"] == [
        {"skill": "[[convolution]]", "mark": None, "comment": None},
        {"skill": "[[cnn-architecture]]", "mark": None, "comment": None},
    ]
    assert document.metadata["questions"][0] == {"kind": "single", "skills": ["convolution"], "options": ["Convolution", "Cross-correlation"]}
    assert "## ❓ Question 1 · Single choice\n*Skill : [[convolution]]*" in document.body
    assert "- [ ] **B.** Cross-correlation" in document.body
    assert "## ❓ Question 3 · Open question" in document.body and "**Your answer :**" in document.body
    assert "Pooling" not in document.body and "correct_options" not in json.dumps(document.metadata)  # no solution in the exam
    solutions = json.loads((vault / ".teach-me" / "solutions" / f"{exam['slug']}.json").read_text(encoding="utf-8"))
    assert solutions == [["A"], ["A", "B"], OPEN["expected_answer"]]
    assert get_course_state(course)["pending_exams"][0]["slug"] == exam["slug"]


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

    assert grade_open_questions(exam["slug"], [GRADE]) == {"graded": [3], "ungraded": []}
    result = correct_exam(exam["slug"], EXPLAIN, comments={"convolution": "Forgot one neutral kernel"})
    assert result["outcomes"] == ["correct", "incomplete", "incomplete"]  # closed questions graded by the server
    assert result["marks"] == {"convolution": 75, "cnn-architecture": 50}
    assert (result["correct"], result["incomplete"], result["wrong"]) == (0.33, 0.67, 0.0)

    document = vault_io.read(vault / exam["path"])
    assert document.metadata["status"] == "corrected"
    assert document.metadata["skills"][0] == {"skill": "[[convolution]]", "mark": 75, "comment": "Forgot one neutral kernel"}
    assert [q["outcome"] for q in document.metadata["questions"]] == result["outcomes"]
    body = document.body
    assert body.index("## ❓ Question 1") < body.index("## ✅ Correction")  # the exam is kept, the correction comes after
    assert "Two convolutions and a dense layer." in body
    assert "> [!Warning] Question 2 : Incomplete answer" in body and "**Solution :** A, B" in body
    assert "Pooling was missing." in body
    state = get_course_state(course)
    assert {s["slug"]: s["latest_mark"] for s in state["skills"]} == {"convolution": 75, "cnn-architecture": 50}
    assert "corrected : 1 correct, 2 incomplete, 0 wrong" in state["sessions"][0]["entries"]


def test_answers_given_in_the_chat_are_written_into_the_file(course, vault):
    exam = _create(course)
    grade_open_questions(exam["slug"], [GRADE])
    result = correct_exam(exam["slug"], EXPLAIN, answers=["b", "A, B", "Some convolutions."])
    assert result["outcomes"] == ["wrong", "correct", "incomplete"]
    body = vault_io.read(vault / exam["path"]).body
    assert "- [x] **B.** Cross-correlation" in body and "- [ ] **A.** Convolution" in body
    assert "- [x] **A.** 1x1" in body and "- [x] **B.** 3x3" in body
    assert body.index("Some convolutions.") < body.index("## ✅ Correction")


def test_a_question_counts_for_each_of_its_skills(course):
    both = {**OPEN, "skills": ["convolution", "cnn-architecture"]}
    exam = _create(course, [SINGLE, both])
    grade_open_questions(exam["slug"], [{"question": 2, "outcome": "wrong", "explanation": "No pooling, no convolution."}])
    result = correct_exam(exam["slug"], EXPLAIN[:1], answers=["A", "Dense layers only."])
    assert result["marks"] == {"convolution": 50, "cnn-architecture": 0}


def test_open_questions_are_graded_before_the_correction(course, vault):
    first, second = {**OPEN, "text": "First"}, {**OPEN, "text": "Second"}
    slug = _create(course, [first, second])["slug"]
    with pytest.raises(ToolError, match=r"open question\(s\) 1, 2 with grade_open_questions"):
        correct_exam(slug, answers=["a", "b"])
    assert grade_open_questions(slug, [{**GRADE, "question": 1}]) == {"graded": [1], "ungraded": [2]}
    assert grade_open_questions(slug, [{**GRADE, "question": 2, "outcome": "wrong"}])["ungraded"] == []
    assert grade_open_questions(slug, [{**GRADE, "question": 2, "outcome": "correct"}])["graded"] == [1, 2]  # grading again replaces
    assert correct_exam(slug, answers=["a", "b"])["outcomes"] == ["incomplete", "correct"]
    assert not (vault / ".teach-me" / "grades" / f"{slug}.json").exists()  # a retake is graded again
    with pytest.raises(ToolError, match="grade_open_questions first"):
        correct_exam(slug, answers=["a", "b"])


def test_grades_check_their_arguments(course):
    slug = _create(course)["slug"]
    with pytest.raises(ToolError, match="from 1 to 3"):
        grade_open_questions(slug, [{**GRADE, "question": 4}])
    with pytest.raises(ToolError, match="closed question"):
        grade_open_questions(slug, [{**GRADE, "question": 1}])
    with pytest.raises(ToolError, match="needs an `outcome`"):
        grade_open_questions(slug, [{**GRADE, "outcome": "perfect"}])
    with pytest.raises(ToolError, match="has no `explanation`"):
        grade_open_questions(slug, [{**GRADE, "explanation": ""}])


def test_correction_needs_the_answers(course):
    exam = _create(course)
    grade_open_questions(exam["slug"], [GRADE])
    with pytest.raises(ToolError, match="give their answers in `answers`"):
        correct_exam(exam["slug"], EXPLAIN)


def test_correction_checks_its_arguments(course):
    slug = _create(course)["slug"]
    grade_open_questions(slug, [GRADE])
    answers = ["A", "A", "text"]
    with pytest.raises(ToolError, match=r"missing question\(s\) 2"):
        correct_exam(slug, EXPLAIN[:1], answers=answers)
    with pytest.raises(ToolError, match="is an open question"):
        correct_exam(slug, [*EXPLAIN, {"question": 3, "explanation": "?"}], answers=answers)
    with pytest.raises(ToolError, match="has no `explanation`"):
        correct_exam(slug, [EXPLAIN[0], {"question": 2, "explanation": ""}], answers=answers)
    with pytest.raises(ToolError, match="one answer per question"):
        correct_exam(slug, EXPLAIN, answers=["A"])
    with pytest.raises(ToolError, match="unknown options Z"):
        correct_exam(slug, EXPLAIN, answers=["Z", "A", "text"])
    with pytest.raises(ToolError, match="doesn't evaluate : nope"):
        correct_exam(slug, EXPLAIN, answers=answers, comments={"nope": "?"})


def test_a_second_correction_never_removes_the_first_one(course, vault):
    exam = _create(course, [SINGLE])
    correct_exam(exam["slug"], [{"question": 1, "explanation": "First correction"}], answers=["B"])
    correct_exam(exam["slug"], [{"question": 1, "explanation": "After the retake"}], answers=["A"])
    body = vault_io.read(vault / exam["path"]).body
    assert body.count("## ✅ Correction (") == 2
    assert body.index("First correction") < body.index("After the retake")
    assert objects.mark_history("alice") == {"convolution": [100]}  # one exam, its latest mark


def test_latest_mark_follows_the_exams(course):
    first = _create(course, [SINGLE])["slug"]
    second = _create(course, [SINGLE])["slug"]
    correct_exam(first, EXPLAIN[:1], answers=["B"])
    correct_exam(second, EXPLAIN[:1], answers=["A"])
    assert objects.mark_history("alice") == {"convolution": [0, 100]}


def test_progress_advice(course):
    assert get_course_state(course)["progress"]["advice"] == []
    save_class(course, "Convolution", "", "Content")
    save_class(course, "Kernels", "", "Content")
    progress = get_course_state(course)["progress"]
    assert progress["classes_since_last_exam"] == 2
    assert "propose an exercise" in progress["advice"][0]

    slug = _create(course, [SINGLE, MULTIPLE])["slug"]
    assert "waiting for an answer" in get_course_state(course)["progress"]["advice"][0]
    correct_exam(slug, EXPLAIN, answers=["B", "C"])
    progress = get_course_state(course)["progress"]
    assert progress["classes_since_last_exam"] == 0
    assert progress["last_corrected_exam"]["wrong"] == 1.0
    assert "re-explain" in progress["advice"][0]


def test_unknown_exam(course):
    with pytest.raises(ToolError, match="Unknown exam"):
        read_exam("nope")
