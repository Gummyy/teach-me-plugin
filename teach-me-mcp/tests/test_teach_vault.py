"""The `teach-vault` command, on the fixture vault of tests/fixtures/teach_them_vault."""

import shutil
from pathlib import Path

import pytest

from teach_me.vault import markdown
from teach_me.vault.cli import main
from teach_me.vault.notes import find_vault

FIXTURE = Path(__file__).parent / "fixtures" / "teach_them_vault"
COURSE = "courses/sql/course-sql.md"


@pytest.fixture
def vault(tmp_path) -> Path:
    """A copy of the fixture vault : its plan is up to date and every check passes."""
    copy = tmp_path / "vault"
    shutil.copytree(FIXTURE, copy)
    return copy


def edit(vault: Path, note: str, old: str, new: str) -> None:
    path = vault / note
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {note}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def check(vault: Path, capsys) -> tuple[int, str]:
    code = main(["check", str(vault)])
    return code, capsys.readouterr().out


# --------------------------------------------------------------------------- #
# markdown
# --------------------------------------------------------------------------- #


def test_links_ignore_code_and_parse_aliases_and_headings():
    text = "[[a]] `[[b]]` [[folder/c#Head\\|Alias]] ![[img/d.png]]\n```\n[[e]]\n```\n[[#Local]]"
    found = [(link.note, link.heading, link.alias) for link in markdown.links(text)]
    assert found == [("a", None, None), ("c", "Head", "Alias"), ("d.png", None, None), ("", "Local", None)]


def test_title_keeps_inline_code():
    assert markdown.title("# Write an `AGENTS.md`\n", "x") == "Write an `AGENTS.md`"


# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #


def test_plan_check_passes_on_an_up_to_date_vault(vault, capsys):
    assert main(["plan", "--check", str(vault)]) == 0
    assert "up to date" in capsys.readouterr().out


def test_plan_follows_the_properties_of_the_steps(vault, capsys):
    edit(vault, "courses/sql/classes/class-joins.md", "duration: 35", "duration: 50")
    edit(vault, "courses/sql/activities/activity-joins-kata.md", "status: proposed", "status: chosen")
    assert main(["plan", "--check", str(vault)]) == 1
    before = (vault / COURSE).read_text(encoding="utf-8")

    assert main(["plan", str(vault)]) == 0
    text = (vault / COURSE).read_text(encoding="utf-8")
    plan = text[text.index("%% plan:start %%") : text.index("%% plan:end %%")]
    extras = text[text.index("%% extras:start %%") : text.index("%% extras:end %%")]
    assert "| 📖 class | 50 |" in plan
    assert "activity-joins-kata" in plan and "activity-joins-kata" not in extras
    assert text.split("%% skills:start %%")[0] == before.split("%% skills:start %%")[0]  # nothing else changes
    assert main(["plan", "--check", str(vault)]) == 0


def test_plan_orders_the_steps_of_a_half_day(vault):
    edit(vault, "courses/sql/exams/quiz-day-2-recall.md", "order: 1", "order: 9")
    main(["plan", str(vault)])
    plan = (vault / COURSE).read_text(encoding="utf-8").split("%% plan:start %%")[1]
    assert plan.index("class-joins") < plan.index("quiz-day-2-recall")


def test_plan_leaves_out_a_missing_block(vault, capsys):
    edit(vault, COURSE, "%% extras:start %%\n", "")
    assert main(["plan", str(vault)]) == 0
    assert "no '%% extras:start %%'" in capsys.readouterr().out


def test_dropped_steps_leave_the_plan(vault):
    edit(vault, "courses/sql/classes/class-joins.md", "status: chosen", "status: dropped")
    main(["plan", str(vault)])
    assert "class-joins" not in (vault / COURSE).read_text(encoding="utf-8").split("%% plan:start %%")[1].split("%% plan:end %%")[0]


# --------------------------------------------------------------------------- #
# check
# --------------------------------------------------------------------------- #


def test_check_passes_on_the_fixture_and_lists_the_postponed_corrections(vault, capsys):
    code, out = check(vault, capsys)
    assert code == 0, out
    assert "presentation-final.md: expected outcome or correction postponed" in out


def test_check_reports_a_broken_link(vault, capsys):
    edit(vault, "courses/sql/classes/class-joins.md", "[[class-select#Content|the first class]]", "[[class-selekt]]")
    code, out = check(vault, capsys)
    assert code == 1
    assert "class-joins.md: [[class-selekt]] → no such note" in out


def test_check_reports_a_broken_heading(vault, capsys):
    edit(vault, "courses/sql/classes/class-joins.md", "class-select#Content", "class-select#Contents")
    code, out = check(vault, capsys)
    assert code == 1 and "no heading 'Contents' in class-select" in out


def test_check_reports_a_broken_link_in_the_properties(vault, capsys):
    edit(vault, "courses/sql/classes/class-joins.md", '"[[skill-joins]]"', '"[[skill-join]]"')
    code, out = check(vault, capsys)
    assert code == 1 and "[[skill-join]] → no such note" in out


def test_check_reports_an_unevaluated_skill(vault, capsys):
    edit(vault, "courses/sql/exams/presentation-final.md", '  - "[[skill-joins]]"\n', "")
    code, out = check(vault, capsys)
    assert code == 1 and "skills/skill-joins.md: evaluated by no chosen quiz" in out


def test_check_reports_a_day_without_recall(vault, capsys):
    edit(vault, "courses/sql/exams/quiz-day-2-recall.md", "order: 1", "order: 9")
    code, out = check(vault, capsys)
    assert code == 1 and "day 2 opens with class-joins, not with a recall quiz" in out


def test_check_reports_a_missing_exam_section(vault, capsys):
    edit(vault, "courses/sql/exams/quiz-day-2-recall.md", "## Correction", "## Grading")
    code, out = check(vault, capsys)
    assert code == 1 and "quiz-day-2-recall.md: missing section(s) Correction" in out


def test_check_reports_a_teacher_link_outside_a_teacher_block(vault, capsys):
    edit(vault, COURSE, "- [[helper-cheat-sheet|Cheat sheet]]", "- [[helper-cheat-sheet|Cheat sheet]]\n- [[instructions-day-1]]")
    code, out = check(vault, capsys)
    assert code == 1 and "course-sql.md: [[instructions-day-1]] → instructions-day-1 is a teacher note" in out


def test_check_reports_an_invalid_frontmatter(vault, capsys):
    edit(vault, "skills/skill-select.md", 'section: "1 · Simple queries"', 'section: "1 · Simple queries')
    code, out = check(vault, capsys)
    assert code == 1 and "skills/skill-select.md: invalid YAML frontmatter" in out


def test_check_reports_a_duplicate_file_name(vault, capsys):
    shutil.copy(vault / "skills/skill-select.md", vault / "projects/skill-select.md")
    code, out = check(vault, capsys)
    assert code == 1 and "same file name as another note" in out


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #


def test_export_builds_the_student_vault(vault, tmp_path, capsys):
    destination = tmp_path / "student"
    assert main(["export", str(vault), str(destination)]) == 0
    assert "Student vault : 11 notes checked, 0 failure(s)." in capsys.readouterr().out

    assert not (destination / "courses/sql/instructions/instructions-day-1.md").exists()
    assert not (destination / ".obsidian/workspace.json").exists()
    assert (destination / ".obsidian/app.json").exists()
    assert (destination / "courses/sql/helpers/cheat-sheet/queries.sql").exists()
    quiz = (destination / "courses/sql/exams/quiz-day-2-recall.md").read_text(encoding="utf-8")
    assert "## Instructions for the students" in quiz and "Expected outcome" not in quiz and "teacher:" not in quiz
    course = (destination / COURSE).read_text(encoding="utf-8")
    assert "For the teacher" not in course and "[[helper-cheat-sheet|Cheat sheet]]" in course


def test_export_turns_the_links_to_teacher_notes_into_text(vault, tmp_path):
    edit(vault, "courses/sql/autonomy/autonomy-first-queries.md", "Use the", "Read [[instructions-day-1|the plan of day 1]]. Use the")
    main(["export", str(vault), str(tmp_path / "student")])
    text = (tmp_path / "student/courses/sql/autonomy/autonomy-first-queries.md").read_text(encoding="utf-8")
    assert "Read the plan of day 1. Use the [[helper-cheat-sheet|cheat sheet]]." in text


def test_export_reports_a_link_broken_by_a_removed_block(vault, tmp_path, capsys):
    edit(vault, "courses/sql/classes/class-joins.md", "class-select#Content", "class-select#Questions to ask the room")
    assert main(["export", str(vault), str(tmp_path / "student")]) == 1
    assert "no heading 'Questions to ask the room' in class-select" in capsys.readouterr().out


def test_export_refuses_a_destination_inside_the_vault_or_existing(vault, tmp_path, capsys):
    assert main(["export", str(vault), str(vault / "student")]) == 1
    (tmp_path / "student").mkdir()
    assert main(["export", str(vault), str(tmp_path / "student")]) == 1
    assert main(["export", str(vault), str(tmp_path / "student"), "--force"]) == 0
    assert "must be outside" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# vault detection
# --------------------------------------------------------------------------- #


def test_find_vault(vault, tmp_path):
    assert find_vault(vault / "courses/sql/classes/class-select.md") == vault.resolve()
    assert find_vault(vault / "skills/skill-select.md") == vault.resolve()
    (tmp_path / "other/courses/x").mkdir(parents=True)
    (tmp_path / "other/courses/x/notes.md").write_text("---\ntype: class\n---\n", encoding="utf-8")
    assert find_vault(tmp_path / "other/courses/x/notes.md") is None
