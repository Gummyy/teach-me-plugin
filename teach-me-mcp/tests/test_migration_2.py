"""Migration 2, on a vault at version 1 : the bases are written again, and the student's version is kept in the backup."""

from teach_me.database import dashboards, migrations
from teach_me.tools import migrate_vault

BROKEN_PLAN = """views:
  - type: table
    name: Plan
    filters:
      and:
        - or:
        - 'type == "class"'
"""


def test_the_bases_are_written_again(course, vault):
    (vault / ".teach-me").mkdir(exist_ok=True)
    (vault / ".teach-me" / "version").write_text("1\n")
    (vault / "bases" / "course.base").write_text(BROKEN_PLAN)
    result = migrate_vault()
    assert result["from"] == 1 and result["to"] == migrations.current_version()
    assert "bases/course.base : written again" in result["changes"]
    assert (vault / "bases" / "course.base").read_text(encoding="utf-8") == dashboards.COURSE_BASE
    assert (vault / result["backup"] / "bases" / "course.base").read_text() == BROKEN_PLAN
    assert (vault / result["backup"] / "Home.md").is_file()
