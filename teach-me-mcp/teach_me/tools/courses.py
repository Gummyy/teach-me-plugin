"""Creating, listing and continuing courses."""

from datetime import datetime
from typing import Optional

from teach_me.database import dashboards, objects, quiz, vault
from teach_me.database import plan as plans
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.project import project_summary
from teach_me.tools import resources as shared
from teach_me.tools.schemas import CourseStatus, PlannedStep, StepUpdate
from teach_me.tools.skill import check_skills, list_skills
from teach_me.tools.users import edit_text

CLASSES_BEFORE_EXERCISE = 3
"""The skill asks for at least one exercise every 3 classes."""
TOO_EASY, TOO_HARD, FAILED = 4.5, 3.5, 2.5
"""A good exam : about 50 % of A, 35 % of B and 15 % of C or D, a mean of about 4 out of 5. Above TOO_EASY it was too easy,
below TOO_HARD too hard, and below FAILED its concepts need to be explained again."""


def _created(document: Document) -> datetime:
    return vault.parse_time(document.metadata.get("created_at")) or datetime.min


def _progress(course: str) -> dict:
    """Cadence and difficulty, computed from the classes and the corrected exams, so that the teacher doesn't have to keep count."""
    exams = list(objects.iter_exams(course))
    last_exam = exams[-1] if exams else None
    since = _created(last_exam) if last_exam else datetime.min
    classes_since = sum(1 for document in objects.iter_documents(course, "classes") if _created(document) > since)

    advice, last = [], None
    corrected = [exam for exam in exams if exam.metadata.get("status") == "corrected" and objects.exam_data(objects.slug(exam), strict=False).get("questions")]
    if corrected:
        exam = corrected[-1]
        grades = [q.get("grade") for q in objects.exam_data(objects.slug(exam), strict=False)["questions"] if q.get("grade") in quiz.GRADES]
        if grades:
            mean = quiz.mean_score(grades)
            shares = {grade: round(grades.count(grade) / len(grades), 2) for grade in quiz.GRADES}
            last = {"slug": objects.slug(exam), "title": exam.metadata.get("title"), "mean": mean, "shares": shares}
            if mean < FAILED:
                advice.append("The last exam failed : re-explain its concepts, then propose an easier exercise on them.")
            elif mean < TOO_HARD:
                advice.append("The last exam was too hard : lower the difficulty of the next one.")
            elif mean >= TOO_EASY:
                advice.append("The last exam was too easy : raise the difficulty of the next one.")
            else:
                advice.append("The difficulty of the last exam was right : keep it.")
    pending = [exam for exam in exams if exam.metadata.get("status") in ("assigned", "filled")]
    if pending:
        advice.append(f"{len(pending)} exam(s) waiting for an answer or a correction : deal with them before creating a new one.")
    elif classes_since >= CLASSES_BEFORE_EXERCISE:
        advice.append(f"{classes_since} classes since the last exercise : propose an exercise before the next class.")
    return {"classes_since_last_exam": classes_since, "last_corrected_exam": last, "advice": advice}


def _project_links(user: str, projects: list[str], missing_ok: bool = False) -> list[str]:
    """The links to projects of the user. With `missing_ok`, a project whose note is missing keeps its link, with a warning : it was already linked."""
    links = []
    for project in projects:
        if missing_ok and not objects.project_file(project).is_file():
            links.append(objects.link_or_name("project", project, objects.project_file(project)))
            continue
        owner = objects.unlink(objects.get_project(project, user).metadata.get("user", ""))
        if owner != user:
            raise ToolError(f"The project '{project}' belongs to '{owner}', not to '{user}'.")
        links.append(objects.link("project", project, objects.project_file(project)))
    return links


def _new_steps(steps: list[PlannedStep], course_skills: list[str], argument: str) -> list[dict]:
    """Validates new steps and gives each a slug, unique among the documents and the plans of every course."""
    taken = {folder: plans.reserved_slugs(folder) for folder in set(objects.STEP_FOLDERS.values())}
    cleaned = []
    for number, step in enumerate(steps, 1):
        step = plans.clean_step(step, course_skills, f"Step {number} of `{argument}`")
        cleaned.append({"slug": plans.new_slug(step["kind"], step["title"], taken[objects.STEP_FOLDERS[step["kind"]]]), **step})
    return cleaned


def create_course(
    user: str,
    subject: str,
    starting_level: str,
    skills: list[str],
    plan: list[PlannedStep],
    projects: Optional[list[str]] = None,
    name: Optional[str] = None,
) -> dict:
    """Creates a course with its plan, and opens its first session. Before calling this tool, you must have created its projects (create_project) and its skills (create_skills), and validated the plan with the student.

    Args:
        user (str): The slug of the user
        subject (str): 2-3 sentences about what the user wants to learn, mixing specific and general subjects
        starting_level (str): 2-3 sentences about the skills the user already has for this course
        skills (list[str]): The slugs of ALL the skills the course will evaluate, as returned by create_skills, in the order of the progression. Exams can only evaluate these skills.
        plan (list[PlannedStep]): The plan of the whole course, in order : every class and exam you foresee, from the first class to the last project exam. Each step gets its note right away, as planned, and the course note shows the plan as a table. Change it later with edit_course.
        projects (Optional[list[str]]): The slugs of the projects this course builds towards. Defaults to None.
        name (Optional[str]): A short name for the course (3-5 words), used for its folder. Defaults to the first words of the subject.

    Returns:
        dict: {"slug", "plan", "warnings"} : the slug of the new course, its steps with their slugs (pass them as `planned` to save_class and create_exam), and what the plan lacks (skills that no exam evaluates, too many classes without an exam) : fix it with edit_course
    """
    objects.get_user(user)
    if not (subject or "").strip():
        raise ToolError("The course needs a non empty `subject`.")
    if not skills:
        raise ToolError("Give the slugs of ALL the skills of the course in `skills` (create them first with create_skills) : exams can only evaluate these skills.")
    if not plan:
        raise ToolError("Give the plan of the whole course in `plan` : every class and exam you foresee, in order. Validate it with the student first.")
    title = (name or "").strip() or " ".join(subject.split()[:5])
    for existing in objects.iter_courses(user):
        if vault.slugify(str(existing.metadata.get("name") or "")) == vault.slugify(title) or objects.course_slug(existing) == vault.slugify(title):
            raise ToolError(
                f"'{user}' already has the course '{objects.course_slug(existing)}' ({existing.metadata.get('name')}, {existing.metadata.get('status') or 'active'}). "
                "Continue it (start_session with `course`), change it with edit_course, or give the new course another `name`."
            )
    course_skills = check_skills(user, skills)
    skill_links = [objects.link("skill", skill, objects.skill_file(skill)) for skill in course_skills]
    project_links = _project_links(user, projects or [])
    steps = _new_steps(plan, course_skills, "plan")

    slug = vault.unique_slug(vault.slugify(title), lambda s: (objects.courses_dir() / s).exists())
    moment = vault.now()
    document = Document(
        objects.course_file(slug),
        {
            "type": "course",
            "name": title,
            "user": objects.link("user", user, objects.user_file(user)),
            "status": "active",
            "subject": subject.strip(),
            "starting_level": (starting_level or "").strip(),
            "created_at": vault.format_time(moment),
            "updated_at": vault.format_time(moment),
            "projects": project_links,
            "skills": skill_links,
        },
        f"## {vault.format_session(moment)}\n\n- Course created",
    )
    dashboards.render_course(document)
    vault.write(document)
    plans.write_plan(slug, steps)
    return {"slug": slug, "plan": plans.with_progress(slug, steps), "warnings": plans.warnings(steps, course_skills)}


def _used_skills(course: str, steps: list[dict]) -> dict[str, list[str]]:
    """Where each skill is used in a course : by the steps of its plan and by its exams."""
    used: dict[str, list[str]] = {}
    for step in steps:
        for skill in step["skills"]:
            used.setdefault(skill, []).append(f"step {step['slug']}")
    for exam in objects.iter_exams(course):
        for question in objects.exam_data(objects.slug(exam), strict=False).get("questions") or []:
            for skill in question.get("skills") or []:
                used.setdefault(skill, []).append(f"exam {objects.slug(exam)}")
    return {skill: list(dict.fromkeys(places)) for skill, places in used.items()}


def edit_course(
    course: str,
    name: Optional[str] = None,
    subject: Optional[str] = None,
    starting_level: Optional[str] = None,
    add_to_starting_level: Optional[str] = None,
    status: Optional[CourseStatus] = None,
    add_skills: Optional[list[str]] = None,
    remove_skills: Optional[list[str]] = None,
    add_projects: Optional[list[str]] = None,
    remove_projects: Optional[list[str]] = None,
    add_steps: Optional[list[PlannedStep]] = None,
    insert_after: Optional[str] = None,
    update_steps: Optional[list[StepUpdate]] = None,
    remove_steps: Optional[list[str]] = None,
) -> dict:
    """Edits a course and its plan. Only what you give changes : lists are changed with add_* / remove_*, the plan step by step, and a text you give replaces the current one, which is returned in `replaced`. The slug of the course never changes.

    Args:
        course (str): The slug of the course
        name (Optional[str]): The new name of the course. Defaults to None.
        subject (Optional[str]): The new subject, replacing the current one. Defaults to None.
        starting_level (Optional[str]): A whole new starting level, replacing the current one. Defaults to None.
        add_to_starting_level (Optional[str]): Sentences appended to the starting level, e.g. a skill the student turned out to have. Defaults to None.
        status (Optional[CourseStatus]): "finished" when the student completed the course, "abandoned" when they gave it up, "active" to resume it. Defaults to None.
        add_skills (Optional[list[str]]): Slugs of skills to add to the course (create them first with create_skills). Defaults to None.
        remove_skills (Optional[list[str]]): Slugs of skills to remove. A skill used by a step of the plan or by an exam can't be removed. Defaults to None.
        add_projects (Optional[list[str]]): Slugs of projects the course now builds towards. Defaults to None.
        remove_projects (Optional[list[str]]): Slugs of projects to unlink from the course. Defaults to None.
        add_steps (Optional[list[PlannedStep]]): New steps for the plan, inserted in this order. Defaults to None.
        insert_after (Optional[str]): The slug of the step after which add_steps go, "" to put them first. Defaults to the end of the plan.
        update_steps (Optional[list[StepUpdate]]): Changes to existing steps : title, description, skills, importance, resources, or a new position with `move_after`. Defaults to None.
        remove_steps (Optional[list[str]]): Slugs of steps to remove from the plan. Only steps not started yet can be removed. Defaults to None.

    Returns:
        dict: {"slug", "name", "status", "subject", "starting_level", "skills", "projects", "plan", "warnings", "replaced"} : the course after the edit, its whole plan with the progress of each step, what the plan lacks, and the previous version of each text you replaced
    """
    arguments = (name, subject, starting_level, add_to_starting_level, status, add_skills, remove_skills, add_projects, remove_projects, add_steps, insert_after, update_steps, remove_steps)
    if all(argument is None for argument in arguments):
        raise ToolError("Nothing to update : give at least one change.")
    document = objects.get_course(course)
    metadata = document.metadata
    user = objects.unlink(metadata.get("user", ""))
    replaced: dict = {}

    if name is not None:
        if not name.strip():
            raise ToolError("The course `name` can't be empty.")
        if name.strip() != metadata.get("name"):
            replaced["name"] = metadata.get("name")
        metadata["name"] = name.strip()
    if subject is not None:
        if not subject.strip():
            raise ToolError("The course `subject` can't be empty.")
        metadata["subject"], previous = edit_text(str(metadata.get("subject") or ""), subject, None)
        if previous is not None:
            replaced["subject"] = previous
    metadata["starting_level"], previous = edit_text(str(metadata.get("starting_level") or ""), starting_level, add_to_starting_level)
    if previous is not None:
        replaced["starting_level"] = previous
    if status is not None:
        if status not in plans.COURSE_STATUSES:
            raise ToolError(f"Unknown status '{status}'. Use one of : {', '.join(plans.COURSE_STATUSES)}.")
        if status != (metadata.get("status") or "active"):
            objects.append_to_session(document, f"Course {status}")
        metadata["status"] = status

    steps = plans.course_plan(document)
    course_skills = objects.course_skills(document)
    if add_skills:
        course_skills += [skill for skill in check_skills(user, add_skills) if skill not in course_skills]
    if remove_skills:
        used = _used_skills(course, steps)
        unknown = [skill for skill in remove_skills if skill not in course_skills]
        if unknown:
            raise ToolError(f"The course doesn't have the skills {', '.join(unknown)}. Skills of the course : {', '.join(course_skills)}.")
        busy = [f"{skill} ({', '.join(used[skill])})" for skill in remove_skills if skill in used]
        if busy:
            raise ToolError(f"These skills are still used : {'; '.join(busy)}. Remove them from the steps first (update_steps) ; a skill evaluated by an exam stays in the course.")
        course_skills = [skill for skill in course_skills if skill not in remove_skills]
    metadata["skills"] = [objects.link_or_name("skill", skill, objects.skill_file(skill)) for skill in course_skills]

    projects = objects.course_projects(document)
    for project in remove_projects or []:
        if project not in projects:
            raise ToolError(f"The course isn't linked to the project '{project}'. Its projects : {', '.join(projects) or 'none'}.")
        projects.remove(project)
    added = [project for project in add_projects or [] if project not in projects]
    metadata["projects"] = _project_links(user, projects, missing_ok=True) + _project_links(user, added)

    for slug in remove_steps or []:
        step = plans.find_step(document, slug)
        if plans.progress(course, step) != "planned":
            raise ToolError(f"The step '{slug}' already has its document : it can't be removed from the plan.")
        steps = [other for other in steps if other["slug"] != slug]
    for number, update in enumerate(update_steps or [], 1):
        slug = (update or {}).get("step")
        step = next((other for other in steps if other["slug"] == slug), None)
        if step is None:
            raise ToolError(f"Update {number} of `update_steps` : unknown step '{slug}'. Steps : {', '.join(other['slug'] for other in steps) or 'none'}.")
        changes = {key: update[key] for key in ("title", "description", "skills", "importance", "resources") if key in update}
        if "skills" in changes and step["kind"] != "class" and plans.progress(course, step) != "planned":
            raise ToolError(f"Update {number} of `update_steps` : the exam '{slug}' was already given, its skills are the ones its questions evaluate.")
        cleaned = plans.clean_step({**step, **changes}, course_skills, f"Update {number} of `update_steps`")
        step.update(cleaned)
        if "resources" in changes and not cleaned.get("resources"):
            step.pop("resources", None)
        if "move_after" in update:
            if update["move_after"] == slug:
                raise ToolError(f"The step '{slug}' can't be moved after itself.")
            steps = plans.insert([other for other in steps if other is not step], [step], update["move_after"])
    if add_steps:
        steps = plans.insert(steps, _new_steps(add_steps, course_skills, "add_steps"), insert_after)
    elif insert_after is not None:
        raise ToolError("`insert_after` places the steps of `add_steps` : give `add_steps` too, or move a step with `move_after` in update_steps.")
    for step in steps:
        plans.check_step_skills(step["skills"], course_skills, f"The step '{step['slug']}'")

    objects.current_session(document)
    dashboards.render_course(document)
    vault.write(document)
    plans.write_plan(course, steps)
    return {
        "slug": course,
        "name": metadata.get("name"),
        "status": metadata.get("status") or "active",
        "subject": metadata.get("subject"),
        "starting_level": metadata.get("starting_level"),
        "skills": course_skills,
        "projects": projects,
        "plan": plans.with_progress(course, steps),
        "warnings": plans.warnings(steps, course_skills),
        "replaced": replaced,
    }


def list_courses(user: str) -> list[dict]:
    """Lists the courses of a user, sorted by most recent activity.

    Args:
        user (str): The slug of the user

    Returns:
        list[dict]: One item per course : {"slug": str, "name": str, "status": "active" | "finished" | "abandoned", "subject": str, "last_activity": str}
    """
    objects.get_user(user)
    courses = []
    for course in objects.iter_courses(user):
        activity = objects.last_activity(course)
        courses.append(
            {
                "slug": objects.course_slug(course),
                "name": str(course.metadata.get("name") or objects.course_slug(course)),
                "status": course.metadata.get("status") or "active",
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
            "slug", "name", "status", "subject", "starting_level",
            "projects": [{"slug", "name", "description", "last_progress"}],
            "skills": [{"slug", "name", "description", "grade", "score"}], the grade coming from the exams of all the courses,
            "sessions": [{"session", "entries"}], the last sessions, most recent first,
            "plan": {"done", "total", "next_steps"} : the number of steps done, and the next steps not done yet ({"slug", "kind", "title", "description", "skills", "importance", "progress"}) : pass the slug of the one you do as `planned` to save_class or create_exam. The whole plan is in the course note,
            "pending_exams": exams whose status is "assigned" or "filled",
            "new_resources": shared resources the student hasn't looked at yet : [{"slug", "title", "url" or "file", "status", "session", "step"}],
            "resources_to_discuss": resources the student marked as seen or wrote notes about, in Obsidian : the same, with their "notes". Ask them what they thought, in one sentence, when the topic of the day allows it,
            "progress": {"classes_since_last_exam", "last_corrected_exam" ({"slug", "title", "mean", "shares"}), "advice"} : what to do next, computed from the classes and the exams,
        }
    """
    document = objects.get_course(course)
    metadata = document.metadata
    skills = list_skills(objects.unlink(metadata.get("user", "")), course)
    sessions = objects.parse_sessions(document.body)[::-1][: max(last_sessions, 0)]
    pending = [
        {
            "slug": objects.slug(exam),
            "title": exam.metadata.get("title"),
            "type": objects.exam_type(exam),
            "status": exam.metadata.get("status"),
            "path": vault.relative(exam.path),
        }
        for exam in objects.iter_exams(course)
        if exam.metadata.get("status") in ("assigned", "filled")
    ]
    steps = plans.with_progress(course, plans.course_plan(document))
    upcoming = [step for step in steps if step["progress"] != "done"]
    resources = [shared.summary(document) for document in objects.iter_resources(course)]
    to_discuss = [resource for resource in resources if resource["status"] == "seen" or (resource["status"] == "new" and resource.get("notes"))]
    return {
        "slug": course,
        "name": metadata.get("name"),
        "status": metadata.get("status") or "active",
        "subject": metadata.get("subject"),
        "starting_level": metadata.get("starting_level"),
        "plan": {"done": len(steps) - len(upcoming), "total": len(steps), "next_steps": upcoming[: plans.NEXT_STEPS]},
        "projects": [project_summary(project) for project in objects.course_projects(document) if objects.linked_note("project", project, objects.project_file(project))],
        "skills": skills,
        "sessions": [{"session": label, "entries": entries} for label, entries in sessions],
        "pending_exams": pending,
        "new_resources": [resource for resource in resources if resource["status"] == "new" and not resource.get("notes")],
        "resources_to_discuss": to_discuss,
        "progress": _progress(course),
    }
