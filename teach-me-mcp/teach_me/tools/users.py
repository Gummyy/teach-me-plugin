"""Identifying and creating users."""

from typing import Literal, Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.schemas import SkillDeclaration

MIN_USERNAME_LENGTH = 2
INTERFACES = ("terminal", "app")
Interface = Literal["terminal", "app"]
"""Where the student follows the course : a terminal shows markdown as raw text, an app or a browser renders it."""


def _validate_skills(skills: list[SkillDeclaration], argument: str) -> list[dict]:
    cleaned, seen = [], set()
    for skill in skills:
        name = str(skill.get("name") or "").strip() if isinstance(skill, dict) else ""
        if not name:
            raise ToolError(f"Every item of `{argument}` needs a non empty 'name'.")
        if name.lower() in seen:
            raise ToolError(f"The skill '{name}' appears twice in `{argument}`.")
        seen.add(name.lower())
        cleaned.append({"name": name, "description": str(skill.get("description") or "").strip()})
    return cleaned


def _validate_interface_preferences(values: dict) -> dict[str, dict[str, str]]:
    cleaned = {}
    for interface, preferences in values.items():
        if interface not in INTERFACES:
            raise ToolError(f"Unknown interface '{interface}'. Use one of : {', '.join(INTERFACES)}.")
        if not isinstance(preferences, dict):
            raise ToolError(f"The preferences of the interface '{interface}' must be a dictionary, e.g. {{\"quizzes\": \"in the chat\"}}.")
        cleaned[interface] = {str(key): str(value) for key, value in preferences.items()}
    return cleaned


def _user_activity(user: Document):
    activities = [objects.last_activity(course) for course in objects.iter_courses(user.slug)]
    activities = [moment for moment in activities if moment is not None]
    return max(activities) if activities else vault.parse_time(user.metadata.get("created_at"))


def list_users() -> list[dict]:
    """Lists the users of the vault, sorted by most recent activity.

    Returns:
        list[dict]: One item per user : {"slug": str, "name": str, "last_activity": str | None}
    """
    users = []
    for user in objects.iter_users():
        activity = _user_activity(user)
        users.append(
            {
                "slug": user.slug,
                "name": str(user.metadata.get("name") or user.slug),
                "last_activity": vault.format_time(activity) if activity else None,
            }
        )
    users.sort(key=lambda user: user["last_activity"] or "", reverse=True)
    return users


def create_user(
    name: str,
    description: Optional[str] = None,
    preferences: Optional[dict[str, str]] = None,
    interface_preferences: Optional[dict[Interface, dict[str, str]]] = None,
) -> str:
    """Creates a user.

    Args:
        name (str): The name of the user. It can be a nickname or anything the user wants to be refered to as
        description (Optional[str]): The description of the user, what they like, whatever doesn't fit in the preferences. Defaults to None.
        preferences (Optional[dict[str, str]]): The preferences of the user that don't depend on the interface (language, tone, ...). Defaults to None.
        interface_preferences (Optional[dict[Interface, dict[str, str]]]): The preferences that depend on the interface ("terminal" or "app"), e.g. {"terminal": {"quizzes": "in the vault"}, "app": {"quizzes": "in the chat"}}. Defaults to None.

    Returns:
        str: The slug of the new user
    """
    name = (name or "").strip()
    if len(name) < MIN_USERNAME_LENGTH:
        raise ToolError(f"The name '{name}' is too short : it needs at least {MIN_USERNAME_LENGTH} characters.")
    slug = vault.unique_slug(vault.slugify(name), lambda s: (objects.users_dir() / f"{s}.md").exists())
    document = Document(
        objects.users_dir() / f"{slug}.md",
        {
            "name": name,
            "created_at": vault.format_time(vault.now()),
            "preferences": dict(preferences or {}),
            "interface_preferences": _validate_interface_preferences(interface_preferences or {}),
            "known_skills": [],
        },
        (description or "").strip(),
    )
    vault.write(document)
    return slug


def edit_user(
    user: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    preferences: Optional[dict[str, str]] = None,
    interface_preferences: Optional[dict[Interface, dict[str, str]]] = None,
    known_skills: Optional[list[SkillDeclaration]] = None,
) -> dict:
    """Edits a user. All values which are left to None won't be updated.

    Args:
        user (str): The slug of the user
        name (Optional[str]): The new name of the user. Defaults to None.
        description (Optional[str]): The new description of the user. Defaults to None.
        preferences (Optional[dict[str, str]]): The new preferences of the user that don't depend on the interface. Replaces all these preferences. Defaults to None.
        interface_preferences (Optional[dict[Interface, dict[str, str]]]): The new preferences of the given interfaces ("terminal" or "app"). Replaces the preferences of each given interface, and leaves the other interface unchanged. Defaults to None.
        known_skills (Optional[list[SkillDeclaration]]): The skills the user already has. Replaces the whole list. Defaults to None.

    Returns:
        dict: The updated user, as returned by `get_user`
    """
    document = objects.get_user(user)
    if name is not None:
        if len(name.strip()) < MIN_USERNAME_LENGTH:
            raise ToolError(f"The name '{name}' is too short : it needs at least {MIN_USERNAME_LENGTH} characters.")
        document.metadata["name"] = name.strip()
    if description is not None:
        document.body = description.strip()
    if preferences is not None:
        document.metadata["preferences"] = dict(preferences)
    if interface_preferences is not None:
        merged = dict(document.metadata.get("interface_preferences") or {})
        merged.update(_validate_interface_preferences(interface_preferences))
        document.metadata["interface_preferences"] = merged
    if known_skills is not None:
        document.metadata["known_skills"] = _validate_skills(known_skills, "known_skills")
    vault.write(document)
    return get_user(user)


def get_user(user: str) -> dict:
    """Retrieves the info of a user.

    Args:
        user (str): The slug of the user

    Returns:
        dict: {"slug", "name", "description", "preferences", "interface_preferences", "known_skills", "created_at"}
    """
    document = objects.get_user(user)
    metadata = document.metadata
    return {
        "slug": document.slug,
        "name": str(metadata.get("name") or document.slug),
        "description": document.body,
        "preferences": metadata.get("preferences") or {},
        "interface_preferences": metadata.get("interface_preferences") or {},
        "known_skills": metadata.get("known_skills") or [],
        "created_at": metadata.get("created_at"),
    }
