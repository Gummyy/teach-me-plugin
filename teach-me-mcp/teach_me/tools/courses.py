"""Creating, listing and continuing courses."""

from datetime import datetime
from typing import Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.project import project_summary
from teach_me.tools.skill import check_skills, list_skills

CLASSES_BEFORE_EXERCISE = 3
"""The skill asks for at least one exercise every 3 classes."""
TARGET_CORRECT, TARGET_WRONG = 0.7, 0.1
"""A good exam : about 66 % of correct answers and less than 9 % of wrong ones."""


def _created(document: Document) -> datetime:
    return vault.parse_time(document.metadata.get("created_at")) or datetime.min


def _progress(course: str) -> dict:
    """Cadence and difficulty, computed from the classes and the corrected exams, so that the teacher doesn't have to keep count."""
    exams = list(objects.iter_exams(course))
    last_exam = exams[-1] if exams else None
    since = _created(last_exam) if last_exam else datetime.min
    classes_since = sum(1 for document in objects.iter_documents(course, "classes") if _created(document) > since)

    advice, last = [], None
    corrected = [exam for exam in exams if exam.metadata.get("status") == "corrected" and exam.metadata.get("questions")]
    if corrected:
        exam = corrected[-1]
        outcomes = [q.get("outcome") for q in exam.metadata["questions"] if q.get("outcome")]
        if outcomes:
            shares = {outcome: round(outcomes.count(outcome) / len(outcomes), 2) for outcome in ("correct", "incomplete", "wrong")}
            last = {"slug": exam.slug, "title": exam.metadata.get("title"), **shares}
            if shares["correct"] == 0 and shares["incomplete"] == 0:
                advice.append("The last exam validated no skill : re-explain its concepts, then propose an easier exercise on them.")
            elif shares["correct"] == 1:
                advice.append("The last exam was fully successful : make the next one harder (it should stay rare).")
            elif shares["wrong"] > TARGET_WRONG * 3 or shares["correct"] < TARGET_CORRECT / 2:
                advice.append("The last exam was too hard : lower the difficulty of the next one.")
            elif shares["correct"] > 0.85:
                advice.append("The last exam was a bit easy : raise the difficulty of the next one.")
            else:
                advice.append("The difficulty of the last exam was right : keep it.")
    pending = [exam for exam in exams if exam.metadata.get("status") in ("assigned", "filled")]
    if pending:
        advice.append(f"{len(pending)} exam(s) waiting for an answer or a correction : deal with them before creating a new one.")
    elif classes_since >= CLASSES_BEFORE_EXERCISE:
        advice.append(f"{classes_since} classes since the last exercise : propose an exercise before the next class.")
    return {"classes_since_last_exam": classes_since, "last_corrected_exam": last, "advice": advice}


def create_course(
    user: str,
    subject: str,
    starting_level: str,
    skills: list[str],
    projects: Optional[list[str]] = None,
    name: Optional[str] = None,
) -> str:
    """Creates a course and opens its first session. Before calling this tool, you must have create its projects (create_project) and its skills (create_skills) first.

    Args:
        user (str): The slug of the user
        subject (str): 2-3 sentences about what the user wants to learn, mixing specific and general subjects
        starting_level (str): 2-3 sentences about the skills the user already has for this course
        skills (list[str]): The slugs of ALL the skills the course will evaluate, as returned by create_skills, in the order of the progression. Exams can only evaluate these skills.
        projects (Optional[list[str]]): The slugs of the projects this course builds towards. Defaults to None.
        name (Optional[str]): A short name for the course (3-5 words), used for its folder. Defaults to the first words of the subject.

    Returns:
        str: The slug of the new course
    """
    objects.get_user(user)
    if not (subject or "").strip():
        raise ToolError("The course needs a non empty `subject`.")
    if not skills:
        raise ToolError("Give the slugs of ALL the skills of the course in `skills` (create them first with create_skills) : exams can only evaluate these skills.")
    skill_links = [vault.link(skill) for skill in check_skills(user, skills)]
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
            "skills": skill_links,
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
            "slug", "name", "subject", "starting_level",
            "projects": [{"slug", "name", "description", "last_progress"}],
            "skills": [{"slug", "name", "description", "latest_mark"}], the latest mark coming from the exams of all the courses,
            "sessions": [{"session", "entries"}], the last sessions, most recent first,
            "pending_exams": exams whose status is "assigned" or "filled",
            "new_resources": shared resources whose status is "new",
            "progress": {"classes_since_last_exam", "last_corrected_exam", "advice"} : what to do next, computed from the classes and the exams,
        }
    """
    document = objects.get_course(course)
    metadata = document.metadata
    skills = list_skills(vault.unlink(metadata.get("user", "")), course)
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
        "projects": [project_summary(vault.unlink(project)) for project in metadata.get("projects") or []],
        "skills": skills,
        "sessions": [{"session": label, "entries": entries} for label, entries in sessions],
        "pending_exams": pending,
        "new_resources": resources,
        "progress": _progress(course),
    }
