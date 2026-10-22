"""Creating and identifying projects and courses."""

from typing import Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.schemas import SkillDeclaration
from teach_me.tools.users import _validate_skills


def create_project(user: str, name: str, description: str) -> str:
    """Creates a personal project of the user, that courses and project exams build towards.

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
    slug = vault.unique_slug(vault.slugify(name), lambda s: (objects.projects_dir() / f"{s}.md").exists())
    document = Document(
        objects.projects_dir() / f"{slug}.md",
        {"name": name.strip(), "user": vault.link(user), "created_at": vault.format_time(vault.now())},
        (description or "").strip(),
    )
    vault.write(document)
    return slug


def create_course(
    user: str,
    subject: str,
    starting_level: str,
    skills: list[SkillDeclaration],
    projects: Optional[list[str]] = None,
    name: Optional[str] = None,
) -> str:
    """Creates a course and opens its first session.

    Args:
        user (str): The slug of the user
        subject (str): 2-3 sentences about what the user wants to learn, mixing specific and general subjects
        starting_level (str): 2-3 sentences about the skills the user already has for this course
        skills (list[SkillDeclaration]): ALL the skills the course will evaluate. Exams can only evaluate skills declared here.
        projects (Optional[list[str]]): The slugs of the projects this course builds towards. Defaults to None.
        name (Optional[str]): A short name for the course (3-5 words), used for its folder. Defaults to the first words of the subject.

    Returns:
        str: The slug of the new course
    """
    objects.get_user(user)
    if not (subject or "").strip():
        raise ToolError("The course needs a non empty `subject`.")
    if not skills:
        raise ToolError("Declare ALL the skills of the course in `skills` : exams can only evaluate declared skills.")
    declared = _validate_skills(skills, "skills")
    project_links = []
    for project in projects or []:
        owner = vault.unlink(objects.get_project(project).metadata.get("user", ""))
        if owner != user:
            raise ToolError(f"The project '{project}' belongs to '{owner}', not to '{user}'.")
        project_links.append(vault.link(project))

    title = (name or "").strip() or " ".join(subject.split()[:5])
    slug = vault.unique_slug(vault.slugify(title), lambda s: (objects.courses_dir() / s).exists())
    moment = vault.now()
    document = Document(
        objects.course_file(slug),
        {
            "name": title,
            "user": vault.link(user),
            "subject": subject.strip(),
            "starting_level": (starting_level or "").strip(),
            "created_at": vault.format_time(moment),
            "updated_at": vault.format_time(moment),
            "projects": project_links,
            "skills": declared,
            "resources": [],
        },
        f"## {vault.format_session(moment)}\n\n- Course created",
    )
    vault.write(document)
    return slug


def list_courses(user: str) -> list[dict]:
    """Lists the courses of a user, sorted by most recent activity.

    Args:
        user (str): The slug of the user

    Returns:
        list[dict]: One item per course : {"slug": str, "name": str, "subject": str, "last_activity": str}
    """
    objects.get_user(user)
    courses = []
    for course in objects.iter_courses(user):
        activity = objects.last_activity(course)
        courses.append(
            {
                "slug": objects.course_slug(course),
                "name": str(course.metadata.get("name") or objects.course_slug(course)),
                "subject": str(course.metadata.get("subject") or ""),
                "last_activity": vault.format_time(activity) if activity else None,
            }
        )
    courses.sort(key=lambda course: course["last_activity"] or "", reverse=True)
    return courses


def get_course_state(course: str, last_sessions: int = 3) -> dict:
    """Retrieves everything the teacher needs to continue a course. Call it before teaching.

    Args:
        course (str): The slug of the course
        last_sessions (int): The number of session entries to return. Defaults to 3.

    Returns:
        dict: {
            "slug", "name", "subject", "starting_level", "projects",
            "skills": [{"name", "description", "latest_mark"}],
            "sessions": [{"session", "entries"}], the last sessions, most recent first,
            "pending_exams": exams whose status is "assigned" or "filled",
            "new_resources": shared resources whose status is "new",
        }
    """
    document = objects.get_course(course)
    metadata = document.metadata
    history = objects.mark_history(course)
    skills = [
        {
            "name": skill.get("name"),
            "description": skill.get("description", ""),
            "latest_mark": (history.get(str(skill.get("name"))) or [None])[-1],
        }
        for skill in metadata.get("skills") or []
        if isinstance(skill, dict)
    ]
    sessions = objects.parse_sessions(document.body)[::-1][: max(last_sessions, 0)]
    pending = [
        {
            "slug": exam.slug,
            "title": exam.metadata.get("title"),
            "type": exam.metadata.get("type"),
            "status": exam.metadata.get("status"),
            "path": vault.relative(exam.path),
        }
        for exam in objects.iter_exams(course)
        if exam.metadata.get("status") in ("assigned", "filled")
    ]
    resources = [
        resource
        for resource in metadata.get("resources") or []
        if isinstance(resource, dict) and resource.get("status", "new") == "new"
    ]
    return {
        "slug": course,
        "name": metadata.get("name"),
        "subject": metadata.get("subject"),
        "starting_level": metadata.get("starting_level"),
        "projects": [vault.unlink(project) for project in metadata.get("projects") or []],
        "skills": skills,
        "sessions": [{"session": label, "entries": entries} for label, entries in sessions],
        "pending_exams": pending,
        "new_resources": resources,
    }
