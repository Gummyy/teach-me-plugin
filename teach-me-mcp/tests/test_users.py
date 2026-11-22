import pytest

from teach_me.database import vault as vault_io
from teach_me.errors import ToolError
from teach_me.tools import create_user, edit_user, get_user, list_users


def test_create_and_get_user(vault):
    slug = create_user("Alice", {"language": "french"}, "Likes photography")
    assert slug == "alice"
    assert (vault / "users" / "user-alice.md").is_file()
    user = get_user("alice")
    assert user["name"] == "Alice"
    assert user["description"] == "Likes photography"
    assert user["preferences"] == {"language": "french"}
    assert user["known_skills"] == []


def test_same_name_gets_a_new_slug(vault):
    assert create_user("Alice", {"language": "english"}) == "alice"
    assert create_user("alice", {"language": "english"}) == "alice-2"


def test_name_too_short(vault):
    with pytest.raises(ToolError, match="too short"):
        create_user("A", {"language": "english"})


def test_edit_user_only_changes_given_values(vault):
    create_user("Alice", {"language": "english"}, "Likes photography")
    user = edit_user("alice", add_known_skills=[{"name": "python", "description": "numpy and pandas"}])
    assert user["description"] == "Likes photography"
    assert user["known_skills"] == [{"name": "python", "description": "numpy and pandas"}]
    assert edit_user("alice", name="Ali")["name"] == "Ali"
    assert edit_user("alice", name="Ali")["slug"] == "alice"  # the slug never changes


def test_edit_user_rejects_duplicated_skills(vault):
    create_user("Alice", {"language": "english"})
    with pytest.raises(ToolError, match="twice"):
        edit_user("alice", add_known_skills=[{"name": "python", "description": ""}, {"name": "Python", "description": ""}])


def test_unknown_user_lists_known_users(vault):
    create_user("Alice", {"language": "english"})
    with pytest.raises(ToolError, match="Known users : alice"):
        get_user("bob")


def test_list_users(vault):
    assert list_users() == []
    create_user("Alice", {"language": "english"})
    create_user("Bob", {"language": "english"})
    assert {user["slug"] for user in list_users()} == {"alice", "bob"}


def test_interface_preferences(vault):
    create_user("Alice", {"language": "english"}, interface_preferences={"terminal": {"quizzes": "vault"}})
    user = edit_user("alice", interface_preferences={"app": {"quizzes": "chat"}})
    assert user["interface_preferences"] == {"terminal": {"quizzes": "vault"}, "app": {"quizzes": "chat"}}
    user = edit_user("alice", interface_preferences={"terminal": {"quizzes": None}})  # removes one preference only
    assert user["interface_preferences"] == {"app": {"quizzes": "chat"}}
    with pytest.raises(ToolError, match="Unknown interface 'phone'"):
        edit_user("alice", interface_preferences={"phone": {"quizzes": "chat"}})
    with pytest.raises(ToolError, match="'in the chat' isn't a valid `quizzes`.*chat, vault"):
        edit_user("alice", interface_preferences={"app": {"quizzes": "in the chat"}})


def test_create_user_needs_a_language(vault):
    with pytest.raises(ToolError, match="needs a `language`"):
        create_user("Alice", {"tone": "casual"})


def test_other_preferences_are_stored_flat(vault):
    create_user("Alice", {"language": "french", "other": {"examples": "from biology"}})
    assert get_user("alice")["preferences"] == {"language": "french", "examples": "from biology"}
    user = edit_user("alice", preferences={"other": {"examples": None, "pace": "slow"}}, interface_preferences={"app": {"other": {"emojis": "few"}}})
    assert user["preferences"] == {"language": "french", "pace": "slow"}
    assert user["interface_preferences"] == {"app": {"emojis": "few"}}
    with pytest.raises(ToolError, match="Unknown key 'quizzes' in `preferences`"):
        edit_user("alice", preferences={"quizzes": "chat"})
    with pytest.raises(ToolError, match="'tone' has its own key"):
        edit_user("alice", preferences={"other": {"tone": "casual"}})


def test_description_is_added_to_or_replaced(vault):
    create_user("Alice", {"language": "english"}, "Likes photography")
    user = edit_user("alice", add_to_description="Has two cats.")
    assert user["description"] == "Likes photography\n\nHas two cats." and user["replaced"] == {}
    user = edit_user("alice", description="Likes hiking")
    assert user["description"] == "Likes hiking"
    assert user["replaced"] == {"description": "Likes photography\n\nHas two cats."}  # what was lost, to check it
    assert edit_user("alice", description="Likes hiking")["replaced"] == {}  # same text : nothing replaced


def test_the_user_note_is_flat(vault):
    create_user("Alice", {"language": "english", "other": {"pace": "slow"}}, interface_preferences={"terminal": {"quizzes": "vault"}})
    edit_user("alice", add_known_skills=[{"name": "python", "description": "numpy and pandas"}, {"name": "sql", "description": ""}])
    metadata = vault_io.read(vault / "users" / "user-alice.md").metadata
    assert list(metadata) == ["type", "name", "created_at", "language", "pace", "terminal_quizzes", "known_skills"]
    assert metadata["known_skills"] == ["python : numpy and pandas", "sql"]
    for name in ("name", "app_emojis"):
        with pytest.raises(ToolError, match="can't be the name of a preference"):
            edit_user("alice", preferences={"other": {name: "x"}})
    with pytest.raises(ToolError, match="can't hold ':'"):
        edit_user("alice", add_known_skills=[{"name": "go : fiber", "description": ""}])


def test_edits_are_merged_not_replaced(vault):
    create_user("Alice", preferences={"language": "french", "tone": "casual"})
    user = edit_user("alice", preferences={"tone": "formal", "other": {"diagrams": "lots"}})
    assert user["preferences"] == {"language": "french", "tone": "formal", "diagrams": "lots"}
    assert edit_user("alice", preferences={"other": {"diagrams": None}})["preferences"] == {"language": "french", "tone": "formal"}

    edit_user("alice", interface_preferences={"terminal": {"quizzes": "vault", "diagrams": "raw"}})
    user = edit_user("alice", interface_preferences={"terminal": {"diagrams": None}})
    assert user["interface_preferences"] == {"terminal": {"quizzes": "vault"}}


def test_known_skills_are_added_and_removed(vault):
    create_user("Alice", {"language": "english"})
    edit_user("alice", add_known_skills=[{"name": "python", "description": "basics"}, {"name": "sql", "description": ""}])
    user = edit_user("alice", add_known_skills=[{"name": "Python", "description": "numpy"}], remove_known_skills=["sql"])
    assert user["known_skills"] == [{"name": "Python", "description": "numpy"}]
    with pytest.raises(ToolError, match="Unknown known skills : go"):
        edit_user("alice", remove_known_skills=["go"])
