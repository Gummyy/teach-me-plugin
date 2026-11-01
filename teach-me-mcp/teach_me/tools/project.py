"""Creating, listing and updating the personal projects of a user."""

from datetime import datetime
from typing import Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.users import edit_text

PROGRESS_HEADING = "## Progress"


def _split_project(body: str) -> tuple[str, str]:
    """A project file holds its description, then the "## Progress" log."""
    description, _, progress = body.partition(PROGRESS_HEADING)
    return description.strip(), progress.strip()


def _summary(document: Document) -> dict:
    description, progress = _split_project(document.body)
    entries = [line[2:] for line in progress.splitlines() if line.startswith("- ")]
    return {
        "slug": objects.slug(document),
        "name": document.metadata.get("name"),
        "description": description,
        "last_progress": entries[-3:],
    }


def project_summary(project: str) -> dict:
    return _summary(objects.get_project(project))


def create_project(user: str, name: str, description: str) -> str:
    """Creates a personal project of the user, that courses and project exams build towards. Always create the project before the skills and the course.

    Args:
        user (str): The slug of the user
        name (str): A short name for the project
        description (str): 5-10 sentences : current state of the project, its goal, the ideas the user already has

    Returns:
        str: The slug of the new project
    """
    objects.get_user(user)
    if not (name or "").strip():
        raise ToolError("The project needs a non empty `name`.")
    slug = vault.unique_slug(vault.slugify(name), lambda s: objects.project_file(s).exists())
    document = Document(
        objects.project_file(slug),
        {"name": name.strip(), "user": objects.link("user", user, objects.user_file(user)), "created_at": vault.format_time(vault.now())},
        (description or "").strip(),
    )
    vault.write(document)
    return slug


def list_projects(user: str) -> list[dict]:
    """Lists the projects of a user, most recently updated first. Call it before creating a project, to check whether the student already has it.

    Args:
        user (str): The slug of the user

    Returns:
        list[dict]: One item per project : {"slug", "name", "description", "last_progress"}
    """
    objects.get_user(user)
    documents = sorted(objects.iter_projects(user), key=lambda document: objects.last_activity(document) or datetime.min, reverse=True)
    return [_summary(document) for document in documents]


def update_project(
    project: str,
    progress: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    add_to_description: Optional[str] = None,
) -> dict:
    """Updates a project as it advances. The progress log only grows : entries are never removed. A text you give (name, description) replaces the current one, which is returned in `replaced`.

    Args:
        project (str): The slug of the project
        progress (Optional[str]): 1-2 sentences about what changed in the project (a step done, a decision, a new problem), added to its dated progress log. Defaults to None.
        name (Optional[str]): The new name of the project. Its slug doesn't change. Defaults to None.
        description (Optional[str]): A whole new description, when the goal or the scope of the project changed. The progress log is kept. Defaults to None.
        add_to_description (Optional[str]): A paragraph appended to the description, e.g. a new feature the student wants, without repeating the description. Defaults to None.

    Returns:
        dict: {"slug", "name", "description", "last_progress", "replaced"} : the project after the update, and the previous version of each text you replaced, e.g. {"description": "..."}
    """
    document = objects.get_project(project)
    if progress is None and name is None and description is None and add_to_description is None:
        raise ToolError("Nothing to update : give a `progress` entry, a new `name`, a new `description` or `add_to_description`.")
    current_description, log = _split_project(document.body)
    replaced = {}
    if name is not None:
        if not name.strip():
            raise ToolError("The project `name` can't be empty.")
        if name.strip() != document.metadata.get("name"):
            replaced["name"] = document.metadata.get("name")
        document.metadata["name"] = name.strip()
    current_description, previous = edit_text(current_description, description, add_to_description)
    if previous is not None:
        replaced["description"] = previous
    if progress is not None and progress.strip():
        entry = f"- {vault.now():%Y-%m-%d} : {' '.join(progress.split())}"
        log = f"{log}\n{entry}".strip()
    document.metadata["updated_at"] = vault.format_time(vault.now())
    document.body = current_description + (f"\n\n{PROGRESS_HEADING}\n\n{log}" if log else "")
    vault.write(document)
    return {**_summary(document), "replaced": replaced}
