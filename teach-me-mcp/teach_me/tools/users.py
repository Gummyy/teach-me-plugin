"""Identifying and creating users."""

from typing import Literal, Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.schemas import InterfacePreferences, NewPreferences, Preferences, SkillDeclaration

MIN_USERNAME_LENGTH = 2
INTERFACES = ("terminal", "app")
Interface = Literal["terminal", "app"]
"""Where the student follows the course : a terminal shows markdown as raw text, an app or a browser renders it."""
PREFERENCE_FIELDS = tuple(key for key in Preferences.__annotations__ if key != "other")
INTERFACE_PREFERENCE_FIELDS = tuple(key for key in InterfacePreferences.__annotations__ if key != "other")
PREFERENCE_CHOICES = {"quizzes": ("chat", "vault"), "diagrams": ("rendered", "raw", "avoid")}


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


def _flatten_preferences(values: dict, fields: tuple[str, ...], argument: str) -> dict[str, Optional[str]]:
    """{"tone": "casual", "other": {"examples": "biology"}} -> {"tone": "casual", "examples": "biology"} : the vault stores the preferences flat."""
    if not isinstance(values, dict):
        raise ToolError(f"`{argument}` must be a dictionary, with the keys {', '.join(fields)} or other.")
    flat: dict[str, Optional[str]] = {}
    for key, value in values.items():
        if key == "other":
            continue
        if key not in fields:
            raise ToolError(f"Unknown key '{key}' in `{argument}`. Use {', '.join(fields)}, or put it in `other`.")
        choices = PREFERENCE_CHOICES.get(key)
        if value is not None and choices and value not in choices:
            raise ToolError(f"'{value}' isn't a valid `{key}` in `{argument}`. Use one of : {', '.join(choices)}.")
        flat[key] = None if value is None else str(value)
    other = values.get("other") or {}
    if not isinstance(other, dict):
        raise ToolError(f"`other` in `{argument}` must be a dictionary of preferences, e.g. {{\"examples\": \"from biology\"}}.")
    for key, value in other.items():
        key = str(key).strip()
        if key in fields or key == "other":
            raise ToolError(f"'{key}' has its own key in `{argument}` : don't put it in `other`.")
        flat[key] = None if value is None else str(value)
    return flat


def _validate_interface_preferences(values: dict) -> dict[str, dict]:
    cleaned = {}
    for interface, preferences in values.items():
        if interface not in INTERFACES:
            raise ToolError(f"Unknown interface '{interface}'. Use one of : {', '.join(INTERFACES)}.")
        cleaned[interface] = _flatten_preferences(preferences, INTERFACE_PREFERENCE_FIELDS, f"interface_preferences.{interface}")
    return cleaned


def edit_text(current: str, new: Optional[str], addition: Optional[str]) -> tuple[str, Optional[str]]:
    """Replaces a text with `new`, then appends `addition` as a new paragraph. Returns the text and the replaced one (None when nothing was lost)."""
    text, replaced = current, None
    if new is not None and new.strip() != current:
        text, replaced = new.strip(), current or None
    if (addition or "").strip():
        text = f"{text}\n\n{addition.strip()}".strip()
    return text, replaced


def merge(current: Optional[dict], changes: dict) -> dict:
    """Applies `changes` to `current` : a None value removes the key, any other value adds or replaces it."""
    merged = dict(current or {})
    for key, value in changes.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def _user_activity(user: Document):
    activities = [objects.last_activity(course) for course in objects.iter_courses(objects.slug(user))]
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
                "slug": objects.slug(user),
                "name": str(user.metadata.get("name") or objects.slug(user)),
                "last_activity": vault.format_time(activity) if activity else None,
            }
        )
    users.sort(key=lambda user: user["last_activity"] or "", reverse=True)
    return users


def create_user(
    name: str,
    preferences: NewPreferences,
    description: Optional[str] = None,
    interface_preferences: Optional[dict[Interface, InterfacePreferences]] = None,
) -> str:
    """Creates a user.

    Args:
        name (str): The name of the user. It can be a nickname or anything the user wants to be referred to as
        preferences (NewPreferences): The preferences of the user that don't depend on the interface. The language is required, e.g. {"language": "french", "tone": "casual"}
        description (Optional[str]): The description of the user, what they like, whatever doesn't fit in the preferences. Defaults to None.
        interface_preferences (Optional[dict[Interface, InterfacePreferences]]): The preferences that depend on the interface ("terminal" or "app"), e.g. {"terminal": {"quizzes": "vault"}, "app": {"quizzes": "chat"}}. Defaults to None.

    Returns:
        str: The slug of the new user
    """
    name = (name or "").strip()
    if len(name) < MIN_USERNAME_LENGTH:
        raise ToolError(f"The name '{name}' is too short : it needs at least {MIN_USERNAME_LENGTH} characters.")
    flat = _flatten_preferences(preferences or {}, PREFERENCE_FIELDS, "preferences")
    if not (flat.get("language") or "").strip():
        raise ToolError("`preferences` needs a `language` : the one the student talks to you in, unless they said otherwise.")
    slug = vault.unique_slug(vault.slugify(name), lambda s: objects.user_file(s).exists())
    document = Document(
        objects.user_file(slug),
        {
            "name": name,
            "created_at": vault.format_time(vault.now()),
            "preferences": merge({}, flat),
            "interface_preferences": {
                interface: merge({}, values)
                for interface, values in _validate_interface_preferences(interface_preferences or {}).items()
            },
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
    add_to_description: Optional[str] = None,
    preferences: Optional[Preferences] = None,
    interface_preferences: Optional[dict[Interface, InterfacePreferences]] = None,
    add_known_skills: Optional[list[SkillDeclaration]] = None,
    remove_known_skills: Optional[list[str]] = None,
) -> dict:
    """Edits a user. Only the values you give change, all the others are kept : the preferences are merged (a null value removes one), `add_*` arguments add to what exists, and a text you give (name, description) replaces the current one, which is returned in `replaced`.

    Args:
        user (str): The slug of the user
        name (Optional[str]): The new name of the user. Defaults to None.
        description (Optional[str]): A whole new description, replacing the current one. To add something you learnt about the student, use add_to_description instead. Defaults to None.
        add_to_description (Optional[str]): A paragraph appended to the description, without repeating it. Defaults to None.
        preferences (Optional[Preferences]): Preferences that don't depend on the interface, to add or change, e.g. {"tone": "casual", "other": {"examples": "from biology"}}. A null value removes that preference. The other preferences are kept. Defaults to None.
        interface_preferences (Optional[dict[Interface, InterfacePreferences]]): Preferences of an interface ("terminal" or "app") to add or change, e.g. {"app": {"quizzes": "chat"}}. A null value removes that preference. The other preferences are kept. Defaults to None.
        add_known_skills (Optional[list[SkillDeclaration]]): Skills the user already has, to add (or to update, for a skill with the same name). Defaults to None.
        remove_known_skills (Optional[list[str]]): Names of known skills to remove. Defaults to None.

    Returns:
        dict: The updated user, as returned by `get_user`, and "replaced" : the previous version of each text you replaced, e.g. {"description": "..."}, to check that nothing was lost
    """
    document = objects.get_user(user)
    replaced = {}
    if name is not None:
        if len(name.strip()) < MIN_USERNAME_LENGTH:
            raise ToolError(f"The name '{name}' is too short : it needs at least {MIN_USERNAME_LENGTH} characters.")
        if name.strip() != document.metadata.get("name"):
            replaced["name"] = document.metadata.get("name")
        document.metadata["name"] = name.strip()
    document.body, previous = edit_text(document.body, description, add_to_description)
    if previous is not None:
        replaced["description"] = previous
    if preferences is not None:
        changes = _flatten_preferences(preferences, PREFERENCE_FIELDS, "preferences")
        document.metadata["preferences"] = merge(document.metadata.get("preferences"), changes)
    if interface_preferences is not None:
        current = dict(document.metadata.get("interface_preferences") or {})
        for interface, changes in _validate_interface_preferences(interface_preferences).items():
            current[interface] = merge(current.get(interface), changes)
        document.metadata["interface_preferences"] = current
    if add_known_skills or remove_known_skills:
        skills = {str(skill.get("name")).lower(): skill for skill in document.metadata.get("known_skills") or [] if isinstance(skill, dict)}
        unknown = [name for name in remove_known_skills or [] if name.lower() not in skills]
        if unknown:
            raise ToolError(f"Unknown known skills : {', '.join(unknown)}. Known skills : {', '.join(s['name'] for s in skills.values()) or 'none'}.")
        for name in remove_known_skills or []:
            skills.pop(name.lower())
        for skill in _validate_skills(add_known_skills or [], "add_known_skills"):
            skills[skill["name"].lower()] = skill
        document.metadata["known_skills"] = list(skills.values())
    vault.write(document)
    return {**get_user(user), "replaced": replaced}


def get_user(user: str) -> dict:
    """Retrieves the info of a user.

    Args:
        user (str): The slug of the user

    Returns:
        dict: {"slug", "name", "description", "preferences", "interface_preferences", "known_skills", "created_at"}. The preferences are flat : the keys given in `other` sit next to the others
    """
    document = objects.get_user(user)
    metadata = document.metadata
    return {
        "slug": user,
        "name": str(metadata.get("name") or user),
        "description": document.body,
        "preferences": metadata.get("preferences") or {},
        "interface_preferences": metadata.get("interface_preferences") or {},
        "known_skills": metadata.get("known_skills") or [],
        "created_at": metadata.get("created_at"),
    }
