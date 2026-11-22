"""Migration 2, on a vault at version 1 : the bases are written again (the student's version is kept in the backup), the user notes become flat, and the project notes show their courses and skills."""

from teach_me.database import dashboards, migrations, vault as vault_io
from teach_me.tools import get_user, migrate_vault


def at_version_1(vault):
    (vault / ".teach-me").mkdir(exist_ok=True)
    (vault / ".teach-me" / "version").write_text("1\n")

BROKEN_PLAN = """views:
  - type: table
    name: Plan
    filters:
      and:
        - or:
        - 'type == "class"'
"""


def test_the_bases_are_written_again(course, vault):
    at_version_1(vault)
    (vault / "bases" / "course.base").write_text(BROKEN_PLAN)
    result = migrate_vault()
    assert result["from"] == 1 and result["to"] == migrations.current_version()
    assert "bases/course.base : written again" in result["changes"]
    assert (vault / "bases" / "course.base").read_text(encoding="utf-8") == dashboards.COURSE_BASE
    assert (vault / result["backup"] / "bases" / "course.base").read_text() == BROKEN_PLAN
    assert (vault / result["backup"] / "Home.md").is_file()


def test_the_user_notes_become_flat(course, vault):
    at_version_1(vault)
    path = vault / "users" / "user-alice.md"
    user = vault_io.read(path)
    user.metadata = {
        "type": "user",
        "name": "Alice",
        "created_at": user.metadata["created_at"],
        "preferences": {"language": "french", "pace": "slow"},
        "interface_preferences": {"terminal": {"quizzes": "vault", "diagrams": None}, "app": {}},
        "known_skills": [{"name": "python", "description": "numpy"}, {"name": "sql", "description": ""}],
    }
    vault_io.write(user)
    assert "users/user-alice.md : preferences and known skills flat" in migrate_vault()["changes"]
    metadata = vault_io.read(path).metadata
    assert {key: metadata[key] for key in ("language", "pace", "terminal_quizzes", "known_skills")} == {
        "language": "french", "pace": "slow", "terminal_quizzes": "vault", "known_skills": ["python : numpy", "sql"]
    }
    assert not any(isinstance(value, dict) for value in metadata.values())
    profile = get_user("alice")
    assert profile["preferences"] == {"language": "french", "pace": "slow"} and profile["interface_preferences"] == {"terminal": {"quizzes": "vault"}}
    assert profile["known_skills"] == [{"name": "python", "description": "numpy"}, {"name": "sql", "description": ""}]


def test_the_project_notes_show_their_views(course, vault):
    at_version_1(vault)
    path = vault / "projects" / "project-pet-classifier.md"
    project = vault_io.read(path)
    project.body = "Classify the pictures of my cats and dogs.\n\n## Progress\n\n- 2026-11-10 : Dataset collected"
    vault_io.write(project)
    assert "projects/project-pet-classifier.md : views of its courses and skills" in migrate_vault()["changes"]
    body = vault_io.read(path).body
    assert body.startswith("%% teach-me:dashboard start %%")
    assert body.index("Classify") < body.index("- 2026-11-10 : Dataset collected") < body.index("## ✏️ My notes")
