import pytest

from teach_me.errors import ToolError
from teach_me.tools import create_user, edit_user, get_user, list_users


def test_create_and_get_user(vault):
    slug = create_user("Alice", "Likes photography", {"language": "french"})
    assert slug == "alice"
    assert (vault / "users" / "alice.md").is_file()
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
    user = edit_user("alice", known_skills=[{"name": "python", "description": "numpy and pandas"}])
    assert user["description"] == "Likes photography"
    assert user["known_skills"] == [{"name": "python", "description": "numpy and pandas"}]
    assert edit_user("alice", name="Ali")["name"] == "Ali"
    assert edit_user("alice", name="Ali")["slug"] == "alice"  # the slug never changes


def test_edit_user_rejects_duplicated_skills(vault):
    create_user("Alice")
    with pytest.raises(ToolError, match="twice"):
        edit_user("alice", known_skills=[{"name": "python", "description": ""}, {"name": "Python", "description": ""}])


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
    user = edit_user("alice", interface_preferences={"terminal": {}})  # clears one interface only
    assert user["interface_preferences"] == {"terminal": {}, "app": {"quizzes": "in the chat"}}
    with pytest.raises(ToolError, match="Unknown interface 'phone'"):
        edit_user("alice", interface_preferences={"phone": {"quizzes": "in the chat"}})


def test_users_created_before_interface_preferences(vault):
    create_user("Alice")
    path = vault / "users" / "alice.md"
    path.write_text(path.read_text(encoding="utf-8").replace("interface_preferences: {}\n", ""), encoding="utf-8")
    assert get_user("alice")["interface_preferences"] == {}
