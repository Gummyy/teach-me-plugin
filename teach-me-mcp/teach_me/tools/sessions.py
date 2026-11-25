"""Starting a session, session log and classes."""

from typing import Optional

from teach_me.database import dashboards, objects, vault
from teach_me.database import plan as plans
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.courses import get_course_state, list_courses
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
    if user is None:
        users = list_users()
        if not users:
            return {**result, "next_step": "There is no user yet : ask the student how they want to be called, then call create_user (in the language they talk to you in) and start_session again."}
        if len(users) > 1:
            return {**result, "users": users, "next_step": "Several users share this vault : ask the student who they are, then call start_session again with `user`."}
        user = users[0]["slug"]

    dashboards.ensure_home()
    profile = get_user(user)
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
    upcoming = state["plan"]["next_steps"]
    if upcoming:
        steps.append(f"Next step of the plan : the {upcoming[0]['kind']} '{upcoming[0]['title']}' : pass planned=\"{upcoming[0]['slug']}\" to save_class or create_exam.")
    else:
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
    """Saves the content of a class, before presenting it.

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
    metadata = {"title": title.strip(), "status": "done", "session": label, "started_at": moment, "updated_at": moment}
    if (summary or "").strip():
        metadata["description"] = summary.strip()
    plans.fill(path, metadata, content)
    class_link = objects.link("class", objects.slug(path), path, alias=title.strip())
    objects.append_to_session(course_document, f"Class {class_link}")
    dashboards.render_course(course_document)
    vault.write(course_document)
    return {"slug": step["slug"], "path": vault.relative(path), "warnings": warnings}
