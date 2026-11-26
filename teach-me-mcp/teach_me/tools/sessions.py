"""Starting a session, session log and classes."""

from typing import Optional

from teach_me.database import dashboards, objects, renames, vault
from teach_me.database import plan as plans
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.courses import get_course_state, list_courses
from teach_me.tools.schemas import ClassStatus
from teach_me.tools.users import Interface, INTERFACES, get_user, list_users


def start_session(interface: Interface, user: Optional[str] = None, course: Optional[str] = None) -> dict:
    """Starts a teaching session : call it first, in every conversation. It does the lookups you would do one by one, and tells you what to do next.

    Call it again with `user` and `course` as soon as you know them.

    Args:
        interface (Interface): Where you are running : "terminal" (Claude Code in a terminal, markdown shown as raw text) or "app" (an app or a browser, markdown rendered)
        user (Optional[str]): The slug of the student. Defaults to the only user of the vault, when there is only one.
        course (Optional[str]): The slug of the course to continue. Defaults to None.

    Returns:
        dict: {"interface", "user", "preferences", "courses", "course", "next_step"} : the student, their preferences for this interface (general ones merged with the interface's ones), their courses, the state of the course (as returned by get_course_state) and what to do next
    """
    if interface not in INTERFACES:
        raise ToolError(f"Unknown interface '{interface}'. Use one of : {', '.join(INTERFACES)}.")
    result: dict = {"interface": interface, "user": None, "preferences": {}, "courses": [], "course": None}
    moved = renames.restore()  # first : the tools find the notes by their names
    if moved:
        vault.warn(f"Put back the notes the student renamed or moved in Obsidian, nothing to do : {'; '.join(moved)}.")
    if user is None:
        users = list_users()
        if not users:
            return {**result, "next_step": "There is no user yet : ask the student how they want to be called, then call create_user (in the language they talk to you in) and start_session again."}
        if len(users) > 1:
            return {**result, "users": users, "next_step": "Several users share this vault : ask the student who they are, then call start_session again with `user`."}
        user = users[0]["slug"]

    dashboards.ensure_home()
    profile = get_user(user)
    restored = objects.refresh_derived(user)  # what the student changed by hand in a grade, a mean or a status of an exam
    if restored:
        vault.warn(f"Restored from the hidden data of the exams, nothing to do : {'; '.join(restored)}.")
    preferences = {**profile["preferences"], **(profile["interface_preferences"].get(interface) or {})}
    result.update({"user": profile, "preferences": preferences, "courses": list_courses(user)})
    if course is None:
        if result["courses"]:
            step = "Identify the course the student wants to continue in `courses`, then call start_session again with `course`. To start a new one, follow 'Initializing a course or a project' in the skill : project, then skills, then course."
        else:
            step = "The student has no course yet : follow 'Initializing a course or a project' in the skill : project, then skills, then course."
        return {**result, "next_step": step}

    document = objects.get_course(course, user)
    owner = objects.unlink(document.metadata.get("user", ""))
    if owner != user:
        raise ToolError(f"The course '{course}' belongs to '{owner}', not to '{user}'.")
    objects.append_to_session(document, f"Session in the {interface}")
    dashboards.render_course(document)  # the views, written again if the student broke them
    vault.write(document)
    for project in objects.course_projects(document):
        objects.render_project(project)
    state = get_course_state(course)
    steps = [" ".join(state["progress"]["advice"]) or "Continue the course where the last session stopped."]
    if state["classes_to_read"]:
        titles = ", ".join(f"'{lesson['title']}'" for lesson in state["classes_to_read"])
        steps.append(f"The student hasn't marked as read the classes {titles} : ask them in one sentence whether they went through them, and call update_class with \"read\" for those they did. Never insist.")
    upcoming = state["plan"]["next_steps"]
    if upcoming:
        tool = {"class": "save_class", "quiz": "create_exam", "deliverable": "create_deliverable"}.get(upcoming[0]["kind"], "save_class")
        steps.append(f"Next step of the plan : the {upcoming[0]['kind']} '{upcoming[0]['title']}' : pass planned=\"{upcoming[0]['slug']}\" to {tool}.")
    elif state["plan"]["done"] == state["plan"]["total"]:
        steps.append("Every step of the plan is done : propose new steps (edit_course `add_steps`), or mark the course finished (edit_course `status`).")
    if state["status"] != "active":
        steps.insert(0, f"This course is {state['status']} : ask the student whether they want to resume it (edit_course status=\"active\").")
    return {**result, "course": state, "next_step": f"Remind the student where they are in a couple of sentences. {' '.join(steps)}"}


def log_session(course: str, entry: str) -> str:
    """Appends an entry to the current session of a course. A new session is started when the last activity on the course is older than 3 hours.

    Classes, exams and shared resources are logged automatically : use this tool for the observations.

    Args:
        course (str): The slug of the course
        entry (str): 1-3 lines : what was done, and the observations that matter for the next sessions

    Returns:
        str: The session the entry was added to (YYYY-MM-DD HH:MM)
    """
    if not (entry or "").strip():
        raise ToolError("The `entry` is empty.")
    vault.check_links(entry, "entry")
    document = objects.get_course(course)
    label = objects.append_to_session(document, entry)
    vault.write(document)
    return label


def save_class(course: str, title: str, summary: str, content: str, planned: Optional[str] = None) -> dict:
    """Saves the content of a class, before presenting it. The class is "new" until the student went through it : then call update_class with "read".

    Args:
        course (str): The slug of the course
        title (str): The title of the class
        summary (str): 2-4 sentences about what is taught. It replaces the description of the step in the plan
        content (str): The class itself, in markdown
        planned (Optional[str]): The slug of the class step of the plan this class is, from get_course_state's `plan.next_steps`. Leave it out only for a class the plan didn't foresee : it is then added to the plan, with a warning. Defaults to None.

    Returns:
        dict: {"slug", "path", "warnings"} : the slug of the class, its path relative to the vault, and the warnings (e.g. a class outside the plan)
    """
    if not (title or "").strip():
        raise ToolError("The class needs a non empty `title`.")
    if not (content or "").strip():
        raise ToolError("The class `content` is empty : send the class itself, in markdown.")
    vault.check_links(content, "content")
    course_document = objects.get_course(course)
    warnings = []
    if planned is not None:
        step = plans.planned_step(course_document, planned, "class")
    else:
        step, warning = plans.add_unplanned(course_document, "class", title.strip(), (summary or "").strip(), [])
        warnings.append(warning)
    path = objects.step_file(course, step)
    label = objects.current_session(course_document)
    moment = vault.format_time(vault.now())
    metadata = {"title": title.strip(), "status": "new", "session": label, "started_at": moment, "updated_at": moment}
    if (summary or "").strip():
        metadata["description"] = summary.strip()
    plans.fill(path, metadata, content)
    class_link = objects.link("class", objects.slug(path), path, alias=title.strip())
    objects.append_to_session(course_document, f"Class {class_link}")
    dashboards.render_course(course_document)
    vault.write(course_document)
    return {"slug": step["slug"], "path": vault.relative(path), "warnings": warnings}


def update_class(course: str, slug: str, status: ClassStatus) -> str:
    """Updates the status of a class : "read" once the student went through it (in the chat or in their vault), "new" when they want to read it again. save_class writes a class as "new". The student can also change it in Obsidian : get_course_state returns the classes still to read.

    Args:
        course (str): The slug of the course
        slug (str): The slug of the class, as returned by save_class or get_course_state
        status (ClassStatus): The new status

    Returns:
        str: The slug of the class
    """
    if status not in objects.CLASS_STATUSES:
        raise ToolError(f"Unknown status '{status}'. Use one of : {', '.join(objects.CLASS_STATUSES)}.")
    document = objects.get_course(course)
    path = objects.step_file(course, {"kind": "class", "slug": slug})
    if not path.is_file():
        known = ", ".join(objects.slug(lesson) for lesson in objects.iter_documents(course, "classes"))
        raise ToolError(f"Unknown class '{slug}' in the course '{course}'. Classes given : {known or 'none'}. Use the slug returned by save_class.")
    lesson = vault.read(path)
    if lesson.metadata.get("status") in (plans.PLANNED, plans.DROPPED):
        raise ToolError(f"The class '{slug}' is {lesson.metadata.get('status')} : it has no content yet. Write it first with save_class (planned=\"{slug}\").")
    if lesson.metadata.get("status") != status:
        lesson.metadata["status"] = status
        lesson.metadata["updated_at"] = vault.format_time(vault.now())
        vault.write(lesson)
    objects.current_session(document)
    vault.write(document)
    return slug
