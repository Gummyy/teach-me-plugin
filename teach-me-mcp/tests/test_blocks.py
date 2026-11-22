from teach_me.database import blocks

MOMENT = "2026-11-22 10:00"


def test_a_block_is_written_before_the_notes():
    body = blocks.replace("Intro\n\n## ✏️ My notes\n\nMine", "history", "Table v1", MOMENT)
    assert body.index("Intro") < body.index("%% teach-me:history start %%") < body.index("## ✏️ My notes")
    assert blocks.content(body, "history") == "Table v1"


def test_a_block_first():
    body = blocks.replace("## 2026-11-22 10:00\n\n- Course created", "dashboard", "Views", MOMENT, first=True)
    assert body.startswith("%% teach-me:dashboard start %%")


def test_an_untouched_block_is_replaced():
    body = blocks.ensure_notes(blocks.replace("", "history", "Table v1", MOMENT))
    body = blocks.replace(body, "history", "Table v2", MOMENT)
    assert blocks.content(body, "history") == "Table v2" and blocks.notes(body) == ""


def test_the_students_edits_move_to_their_notes():
    body = blocks.ensure_notes(blocks.replace("", "history", "Table v1", MOMENT))
    body = body.replace("Table v1", "Table v1, with my comment")
    body = blocks.replace(body, "history", "Table v2", MOMENT)
    assert blocks.content(body, "history") == "Table v2"
    notes = blocks.notes(body)
    assert notes.startswith("> [!quote]- Your version of the history, replaced by teach-me on 2026-11-22 10:00")
    assert "> Table v1, with my comment" in notes


def test_a_half_deleted_block_is_written_again():
    body = blocks.replace("", "history", "Table v1", MOMENT)
    body = body.split("%% teach-me:history end")[0]  # the end marker was deleted
    body = blocks.replace(body, "history", "Table v2", MOMENT)
    assert body.count("%% teach-me:history start %%") == 1 and blocks.content(body, "history") == "Table v2"
    assert "Table v1" in body  # left as the student's text


def test_the_notes_of_a_course_come_before_its_log():
    body = blocks.ensure_notes("Views\n\n## 2026-11-22 10:00\n\n- Course created")
    assert body.index("## ✏️ My notes") < body.index("## 2026-11-22 10:00")
    moved = blocks.add_to_notes(body, "Old", "Title")
    assert moved.index("## ✏️ My notes") < moved.index("> Old") < moved.index("## 2026-11-22 10:00")
