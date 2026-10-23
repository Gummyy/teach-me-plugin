"""External contents shared with the student."""

from typing import Literal, Optional

from teach_me.database import objects, vault
from teach_me.errors import ToolError


def _find(resources: list, title: str) -> Optional[dict]:
    for resource in resources:
        if isinstance(resource, dict) and str(resource.get("title", "")).strip().lower() == title.strip().lower():
            return resource
    return None


def share_resource(
    course: str,
    title: str,
    web_url: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """Remembers an external content shared with the student during the current session. At least one of web_url / file_path is required. Sharing an already known resource again updates its session, and makes a dropped resource new again.

    Args:
        course (str): The slug of the course
        title (str): A short description, specific enough to find the content again (author, episode, timestamps)
        web_url (Optional[str]): The URL of an online resource. Defaults to None.
        file_path (Optional[str]): The path of a local file. Takes priority over web_url. Defaults to None.

    Returns:
        str: The title of the resource
    """
    if not (title or "").strip():
        raise ToolError("The resource needs a non empty `title`.")
    if not (web_url or "").strip() and not (file_path or "").strip():
        raise ToolError("Give the location of the resource : `web_url` for an online resource, `file_path` for a local file.")
    location = {"file_path": file_path.strip()} if (file_path or "").strip() else {"web_url": web_url.strip()}

    document = objects.get_course(course)
    resources = document.metadata.setdefault("resources", [])
    if resources is None:
        resources = document.metadata["resources"] = []
    label = objects.current_session(document)
    resource = _find(resources, title) or next(
        (r for r in resources if isinstance(r, dict) and any(r.get(key) == value for key, value in location.items())),
        None,
    )
    if resource is None:
        resource = {"title": title.strip(), **location, "status": "new", "created_at": vault.format_time(vault.now())}
        resources.append(resource)
    resource["session"] = label
    if resource.get("status") == "dropped":
        resource["status"] = "new"

    target = location.get("file_path") or location.get("web_url")
    objects.append_to_session(document, f"Shared [{title.strip()}]({target})")
    vault.write(document)
    return str(resource["title"])


def update_resource(course: str, title: str, status: Literal["new", "explained", "dropped"]) -> str:
    """Updates the status of a shared resource : "explained" once the student has engaged with it, "dropped" when it is no longer relevant. Only "new" resources are returned by get_course_state.

    Args:
        course (str): The slug of the course
        title (str): The title of the resource
        status (Literal["new", "explained", "dropped"]): The new status

    Returns:
        str: The title of the resource
    """
    if status not in objects.RESOURCE_STATUSES:
        raise ToolError(f"Unknown status '{status}'. Use one of : {', '.join(objects.RESOURCE_STATUSES)}.")
    document = objects.get_course(course)
    resources = document.metadata.get("resources") or []
    resource = _find(resources, title)
    if resource is None:
        titles = [str(r.get("title")) for r in resources if isinstance(r, dict)]
        raise ToolError(f"Unknown resource '{title}'. Resources of this course : {', '.join(titles) or 'none'}.")
    resource["status"] = status
    objects.current_session(document)
    vault.write(document)
    return str(resource["title"])
