import pytest

from teach_me.database import objects
from teach_me.errors import ToolError
from teach_me.tools import correct_exam, create_exam, get_course_state, report_card, share_resource, update_resource


def test_share_and_update_resource(course):
    share_resource(course, "3Blue1Brown - But what is a convolution ?", web_url="https://www.youtube.com/watch?v=KuXjwB4LzSA")
    resources = get_course_state(course)["new_resources"]
    assert len(resources) == 1
    assert resources[0]["web_url"] == "https://www.youtube.com/watch?v=KuXjwB4LzSA"

    update_resource(course, "3blue1brown - but what is a convolution ?", "explained")  # case insensitive
    assert get_course_state(course)["new_resources"] == []


def test_unprocessed_resource(course):
    share_resource(course, "Old podcast", web_url="https://example.com/old")
    update_resource(course, "Old podcast", "unprocessed")
    assert get_course_state(course)["new_resources"] == []
    share_resource(course, "Old podcast", web_url="https://example.com/old")  # relevant again
    assert [r["title"] for r in get_course_state(course)["new_resources"]] == ["Old podcast"]


def test_sharing_again_doesnt_duplicate(course):
    share_resource(course, "Video", web_url="https://example.com")
    share_resource(course, "Same video", web_url="https://example.com")
    assert len(objects.get_course(course).metadata["resources"]) == 1


def test_file_path_takes_priority(course):
    share_resource(course, "Notes", web_url="https://example.com", file_path="notes.pdf")
    resource = objects.get_course(course).metadata["resources"][0]
    assert resource["file_path"] == "notes.pdf" and "web_url" not in resource


def test_resource_needs_a_location(course):
    with pytest.raises(ToolError, match="location"):
        share_resource(course, "Video")


def test_unknown_resource(course):
    with pytest.raises(ToolError, match="Unknown resource"):
        update_resource(course, "Nope", "explained")


def test_report_card(course, vault):
    empty = report_card(course)
    assert "**0/2** skills evaluated" in empty and "No exam yet." in empty

    question = {"kind": "single", "text": "?", "skill": "convolution", "options": ["Yes", "No"], "correct_options": ["A"]}
    slug = create_exam(course, "Quiz | 1", "quiz", [question, question])["slug"]
    correct_exam(slug, [{"explanation": "."}, {"explanation": "."}], answers=["A", "B"])
    card = report_card(course)
    assert "**1/2** skills evaluated, average of the latest marks : **50/100**" in card
    assert "| convolution | Computes and interprets a 2D convolution | 50 | 50 |" in card
    assert f"[[{slug}\\|Quiz \\| 1]]" in card  # pipes are escaped in tables
    assert (vault / "courses" / course / "report_card.md").is_file()
