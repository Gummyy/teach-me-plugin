import pytest

from teach_me.database import objects, vault
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


def test_share_and_update_resource(course):
    slug = share_resource(course, "3Blue1Brown - But what is a convolution ?", web_url="https://www.youtube.com/watch?v=KuXjwB4LzSA")
    assert slug == "3blue1brown-but-what-is-a-convolution"
    resources = get_course_state(course)["new_resources"]
    assert len(resources) == 1
    assert resources[0]["web_url"] == "https://www.youtube.com/watch?v=KuXjwB4LzSA" and resources[0]["slug"] == slug

    assert update_resource(course, slug, "explained") == slug
    assert get_course_state(course)["new_resources"] == []


def test_resources_have_unique_slugs(course):
    assert share_resource(course, "Video", web_url="https://example.com/1") == "video"
    assert share_resource(course, "Video !", web_url="https://example.com/2") == "video-2"


def test_resources_shared_before_the_slugs(course):
    document = objects.get_course(course)
    document.metadata["resources"] = [{"title": "Old video", "web_url": "https://example.com", "status": "new"}]
    vault.write(document)
    assert get_course_state(course)["new_resources"][0]["slug"] == "old-video"
    update_resource(course, "old-video", "explained")
    assert objects.get_course(course).metadata["resources"][0] == {"title": "Old video", "web_url": "https://example.com", "status": "explained", "slug": "old-video"}


def test_unprocessed_resource(course):
    share_resource(course, "Old podcast", web_url="https://example.com/old")
    update_resource(course, "old-podcast", "unprocessed")
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
    share_resource(course, "Video", web_url="https://example.com")
    with pytest.raises(ToolError, match=r"Unknown resource 'nope'.*video \(Video\)"):
        update_resource(course, "nope", "explained")


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
    assert (vault / "courses" / course / "report-card-computer-vision.md").is_file()
