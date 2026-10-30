import pytest

from teach_me.errors import ToolError
from teach_me.tools import create_user, edit_user, get_user, list_users


def test_create_and_get_user(vault):
    slug = create_user("Alice", "Likes photography", {"language": "french"})
    assert slug == "alice"
    assert (vault / "users" / "user-alice.md").is_file()
    user = get_user("alice")
    assert user["name"] == "Alice"
    assert user["description"] == "Likes photography"
    assert user["preferences"] == {"language": "french"}
    assert user["known_skills"] == []


def test_same_name_gets_a_new_slug(vault):
    assert create_user("Alice") == "alice"
    assert create_user("alice") == "alice-2"


def test_name_too_short(vault):
    with pytest.raises(ToolError, match="too short"):
        create_user("A")


def test_edit_user_only_changes_given_values(vault):
    create_user("Alice", "Likes photography")
    user = edit_user("alice", add_known_skills=[{"name": "python", "description": "numpy and pandas"}])
    assert user["description"] == "Likes photography"
    assert user["known_skills"] == [{"name": "python", "description": "numpy and pandas"}]
    assert edit_user("alice", name="Ali")["name"] == "Ali"
    assert edit_user("alice", name="Ali")["slug"] == "alice"  # the slug never changes


def test_edit_user_rejects_duplicated_skills(vault):
    create_user("Alice")
    with pytest.raises(ToolError, match="twice"):
        edit_user("alice", add_known_skills=[{"name": "python", "description": ""}, {"name": "Python", "description": ""}])


def test_unknown_user_lists_known_users(vault):
    create_user("Alice")
    with pytest.raises(ToolError, match="Known users : alice"):
        get_user("bob")


def test_list_users(vault):
    assert list_users() == []
    create_user("Alice")
    create_user("Bob")
    assert {user["slug"] for user in list_users()} == {"alice", "bob"}


def test_interface_preferences(vault):
    create_user("Alice", interface_preferences={"terminal": {"quizzes": "in the vault"}})
    user = edit_user("alice", interface_preferences={"app": {"quizzes": "in the chat"}})
    assert user["interface_preferences"] == {"terminal": {"quizzes": "in the vault"}, "app": {"quizzes": "in the chat"}}
    user = edit_user("alice", interface_preferences={"terminal": {"quizzes": None}})  # removes one preference only
    assert user["interface_preferences"] == {"terminal": {}, "app": {"quizzes": "in the chat"}}
    with pytest.raises(ToolError, match="Unknown interface 'phone'"):
        edit_user("alice", interface_preferences={"phone": {"quizzes": "in the chat"}})


def test_users_created_before_interface_preferences(vault):
    create_user("Alice")
    path = vault / "users" / "user-alice.md"
    path.write_text(path.read_text(encoding="utf-8").replace("interface_preferences: {}\n", ""), encoding="utf-8")
    assert get_user("alice")["interface_preferences"] == {}


def test_edits_are_merged_not_replaced(vault):
    create_user("Alice", preferences={"language": "french", "tone": "casual"})
    user = edit_user("alice", preferences={"tone": "formal", "diagrams": "lots"})
    assert user["preferences"] == {"language": "french", "tone": "formal", "diagrams": "lots"}
    assert edit_user("alice", preferences={"diagrams": None})["preferences"] == {"language": "french", "tone": "formal"}

    edit_user("alice", interface_preferences={"terminal": {"quizzes": "in the vault", "classes": "in the vault"}})
    user = edit_user("alice", interface_preferences={"terminal": {"classes": None}})
    assert user["interface_preferences"] == {"terminal": {"quizzes": "in the vault"}}


def test_known_skills_are_added_and_removed(vault):
    create_user("Alice")
    edit_user("alice", add_known_skills=[{"name": "python", "description": "basics"}, {"name": "sql", "description": ""}])
    user = edit_user("alice", add_known_skills=[{"name": "Python", "description": "numpy"}], remove_known_skills=["sql"])
    assert user["known_skills"] == [{"name": "Python", "description": "numpy"}]
    with pytest.raises(ToolError, match="Unknown known skills : go"):
        edit_user("alice", remove_known_skills=["go"])
