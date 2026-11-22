"""External contents shared with the student.

Each resource is a note of its own, `courses/<course>/resources/resource-<slug>.md` : its link or file
and its status in the properties, why it is worth a look in its body, and the student's thoughts in its
"My notes" section. The student changes its status themselves in Obsidian (the course note shows the
resources as a board), or tells the teacher, who calls update_resource.

    new : shared, not looked at yet      seen : the student had a look, not discussed yet
    discussed : talked about it          dropped : not relevant anymore
"""

from typing import Literal, Optional

from teach_me.database import blocks, objects, vault
from teach_me.database import plan as plans
from teach_me.database.vault import Document
from teach_me.errors import ToolError

ResourceStatus = Literal["new", "seen", "discussed", "dropped"]


def _location(document: Document) -> dict:
    metadata = document.metadata
    return {key: metadata[key] for key in ("url", "file") if metadata.get(key)}


def summary(document: Document) -> dict:
    """A resource, as the tools return it."""
    metadata = document.metadata
    found = {"slug": objects.slug(document), "title": metadata.get("title"), **_location(document), "status": metadata.get("status"), "session": metadata.get("session")}
    if metadata.get("step"):
        found["step"] = objects.unlink(metadata["step"])
    notes = blocks.notes(document.body)
    if notes:
        found["notes"] = notes
    return found


def _find(course: str, title: str, location: dict) -> Optional[Document]:
    for document in objects.iter_resources(course):
        if str(document.metadata.get("title", "")).strip().lower() == title.strip().lower():
            return document
        if any(document.metadata.get(key) == value for key, value in location.items()):
            return document
    return None


def share_resource(
    course: str,
    title: str,
    web_url: Optional[str] = None,
    file_path: Optional[str] = None,
    description: Optional[str] = None,
    step: Optional[str] = None,
) -> str:
    """Remembers an external content shared with the student during the current session, as a note of the course. At least one of web_url / file_path is required. Sharing an already known resource again updates its session, and makes a dropped resource new again.

    Args:
        course (str): The slug of the course
        title (str): A short description, specific enough to find the content again (author, episode, timestamps)
        web_url (Optional[str]): The URL of an online resource. Defaults to None.
        file_path (Optional[str]): The path of a local file. Takes priority over web_url. Defaults to None.
        description (Optional[str]): 1-2 sentences : why it is worth a look, and what to pay attention to. Defaults to None.
        step (Optional[str]): The slug of the step of the plan (class or exam) it goes with, when there is one. Defaults to None.

    Returns:
        str: The slug of the resource, to give to update_resource
    """
    if not (title or "").strip():
        raise ToolError("The resource needs a non empty `title`.")
    if not (web_url or "").strip() and not (file_path or "").strip():
        raise ToolError("Give the location of the resource : `web_url` for an online resource, `file_path` for a local file.")
    title = title.strip()
    location = {"file": file_path.strip()} if (file_path or "").strip() else {"url": web_url.strip()}
    vault.check_links(description or "", "description")

    course_document = objects.get_course(course)
    step_link = None
    if step is not None:
        found = plans.find_step(course_document, step)
        step_link = objects.link("step", step, objects.step_file(course, found))
    label = objects.current_session(course_document)
    moment = vault.format_time(vault.now())
    document = _find(course, title, location)
    if document is None:
        taken = {objects.slug(path) for path in objects.courses_dir().glob(f"*/resources/{objects.PREFIXES['resource']}*.md")}
        slug = vault.unique_slug(vault.slugify(title), lambda candidate: candidate in taken)
        metadata = {"type": "resource", "course": objects.course_link(course), "title": title, **location, "status": "new"}
        if step_link:
            metadata["step"] = step_link
        metadata.update({"session": label, "created_at": moment, "updated_at": moment})
        document = Document(objects.resource_file(course, slug), metadata, blocks.ensure_notes((description or "").strip()))
    else:
        document.metadata["session"] = label
        document.metadata["updated_at"] = moment
        if document.metadata.get("status") == "dropped":
            document.metadata["status"] = "new"
        if step_link:
            document.metadata["step"] = step_link
    vault.write(document)

    resource_link = objects.link("resource", objects.slug(document), document.path, alias=title)
    objects.append_to_session(course_document, f"Shared {resource_link}")
    vault.write(course_document)
    return objects.slug(document)


def update_resource(course: str, resource: str, status: ResourceStatus) -> str:
    """Updates the status of a shared resource : "seen" when the student says they had a look, "discussed" once you talked about it together, "dropped" when it is no longer relevant. The student can also change it in Obsidian : get_course_state returns the resources they have seen and the notes they wrote, to talk about.

    Args:
        course (str): The slug of the course
        resource (str): The slug of the resource, as returned by share_resource or get_course_state
        status (ResourceStatus): The new status

    Returns:
        str: The slug of the resource
    """
    if status not in objects.RESOURCE_STATUSES:
        raise ToolError(f"Unknown status '{status}'. Use one of : {', '.join(objects.RESOURCE_STATUSES)}.")
    document = objects.get_course(course)
    path = objects.resource_file(course, resource)
    if not path.is_file():
        known = ", ".join(f"{objects.slug(r)} ({r.metadata.get('title')})" for r in objects.iter_resources(course))
        raise ToolError(f"Unknown resource '{resource}'. Resources of this course : {known or 'none'}. Use the slug returned by share_resource.")
    found = vault.read(path)
    found.metadata["status"] = status
    found.metadata["updated_at"] = vault.format_time(vault.now())
    vault.write(found)
    objects.current_session(document)
    vault.write(document)
    return resource
