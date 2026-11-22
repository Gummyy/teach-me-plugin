import pytest

from teach_me.database import objects, vault
from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import (
    correct_exam,
    create_exam,
    get_course_state,
    grade_questions,
    report_card,
    share_resource,
    submit_answers,
    update_resource,
)


def test_share_and_update_resource(course, vault):
    slug = share_resource(course, "3Blue1Brown - But what is a convolution ?", web_url="https://www.youtube.com/watch?v=KuXjwB4LzSA", description="The best animation of a kernel.", step="convolution")
    assert slug == "3blue1brown-but-what-is-a-convolution"
    note = vault_io.read(vault / "courses/computer-vision/resources/resource-3blue1brown-but-what-is-a-convolution.md")
    assert note.metadata["type"] == "resource" and note.metadata["course"] == "[[course-computer-vision]]"
    assert note.metadata["url"] == "https://www.youtube.com/watch?v=KuXjwB4LzSA" and note.metadata["status"] == "new"
    assert note.metadata["step"] == "[[class-convolution]]"
    assert note.body.startswith("The best animation of a kernel.") and note.body.endswith("## ✏️ My notes")
    assert "resources" not in objects.get_course(course).metadata
    assert f"Shared [[resource-{slug}|3Blue1Brown - But what is a convolution ?]]" in get_course_state(course)["sessions"][0]["entries"]
    resources = get_course_state(course)["new_resources"]
    assert len(resources) == 1 and resources[0]["slug"] == slug and resources[0]["step"] == "convolution"

    assert update_resource(course, slug, "discussed") == slug
    assert get_course_state(course)["new_resources"] == []


def test_what_the_student_did_in_obsidian_is_returned(course, vault):
    seen = share_resource(course, "Video", web_url="https://example.com/1")
    noted = share_resource(course, "Podcast", web_url="https://example.com/2")
    share_resource(course, "Book", web_url="https://example.com/3")
    seen_path = vault / f"courses/computer-vision/resources/resource-{seen}.md"
    seen_path.write_text(seen_path.read_text(encoding="utf-8").replace("status: new", "status: seen"), encoding="utf-8")  # dragged on the board
    noted_path = vault / f"courses/computer-vision/resources/resource-{noted}.md"
    noted_path.write_text(noted_path.read_text(encoding="utf-8") + "\nToo long, but the part on strides was great.\n", encoding="utf-8")
    state = get_course_state(course)
    assert [r["slug"] for r in state["new_resources"]] == ["book"]
    assert sorted((r["slug"], r.get("notes")) for r in state["resources_to_discuss"]) == [("podcast", "Too long, but the part on strides was great."), ("video", None)]


def test_resources_have_unique_slugs(course):
    assert share_resource(course, "Video", web_url="https://example.com/1") == "video"
    assert share_resource(course, "Video !", web_url="https://example.com/2") == "video-2"


def test_dropped_resource(course):
    share_resource(course, "Old podcast", web_url="https://example.com/old")
    update_resource(course, "old-podcast", "dropped")
    assert get_course_state(course)["new_resources"] == []
    share_resource(course, "Old podcast", web_url="https://example.com/old")  # relevant again
    assert [r["title"] for r in get_course_state(course)["new_resources"]] == ["Old podcast"]
    with pytest.raises(ToolError, match="Unknown status"):
        update_resource(course, "old-podcast", "unprocessed")


def test_sharing_again_doesnt_duplicate(course):
    share_resource(course, "Video", web_url="https://example.com")
    share_resource(course, "Same video", web_url="https://example.com")
    assert len(list(objects.iter_resources(course))) == 1


def test_file_path_takes_priority(course):
    share_resource(course, "Notes", web_url="https://example.com", file_path="notes.pdf")
    resource = next(objects.iter_resources(course)).metadata
    assert resource["file"] == "notes.pdf" and "url" not in resource


def test_resource_needs_a_location(course):
    with pytest.raises(ToolError, match="location"):
        share_resource(course, "Video")
    with pytest.raises(ToolError, match="Unknown step 'nope'"):
        share_resource(course, "Video", web_url="https://example.com", step="nope")


def test_unknown_resource(course):
    share_resource(course, "Video", web_url="https://example.com")
    with pytest.raises(ToolError, match=r"Unknown resource 'nope'.*video \(Video\)"):
        update_resource(course, "nope", "discussed")


def test_report_card(course, vault):
    empty = report_card(course)
    assert "**0/2** skills evaluated" in empty and "No exam yet." in empty

    question = {"kind": "single", "text": "?", "skills": ["convolution"], "options": ["Yes", "No"], "correct_options": ["A"]}
    slug = create_exam(course, "Quiz | 1", "quiz", [question, question])["slug"]
    submit_answers(slug, ["A", "B"])
    grade_questions(slug, [{"question": 1, "explanation": "."}, {"question": 2, "explanation": "."}])
    correct_exam(slug)
    card = report_card(course)
    assert "**1/2** skills evaluated, average grade : **B** (3.0/5)" in card  # A and D
    assert "| [[skill-convolution\\|convolution]] | Computes and interprets a 2D convolution | B (3.0/5) | B |" in card
    assert "[[quiz-quiz-1\\|Quiz / 1]]" in card  # an alias can't contain a pipe, and the link's pipe is escaped in tables
    assert not (vault / "courses" / course / "report-card-computer-vision.md").exists()  # the course note shows it, always up to date
