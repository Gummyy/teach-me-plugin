"""Deliverables : the milestones of a project, built by the student on their own over several sessions.

    create_deliverable -> (the student works) -> checkin_deliverable at each session -> correct_deliverable

A course has at most one deliverable in progress : it runs alongside the classes and the quizzes, and never blocks them.
The milestones are graded once, at the end. The check-ins give feedback, hints when needed, and the next goals.
"""

from typing import Optional

from teach_me.database import dashboards, objects, vault
from teach_me.database import deliverable as deliverables
from teach_me.database import plan as plans
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.project import update_project
from teach_me.tools.schemas import Difficulty, Milestone


def _solutions_file(deliverable: str):
    """The expected outcomes and the hints, hidden from the student, as the solutions of a quiz."""
    return vault.vault_path() / ".teach-me" / "solutions" / f"{deliverable}.json"


def _solutions(deliverable: str, count: int) -> list[dict]:
    solutions = vault.read_json(_solutions_file(deliverable))
    if not isinstance(solutions, list) or len(solutions) != count:
        raise ToolError(f"The expected outcomes of the deliverable '{deliverable}' are missing ({vault.relative(_solutions_file(deliverable))}) : restore the file from the git history of the vault.")
    return solutions


def _data(document: Document) -> dict:
    data = objects.exam_data(objects.slug(document))
    if data.get("type") != "deliverable" or not data.get("questions"):
        raise ToolError(f"'{objects.slug(document)}' is a quiz, not a deliverable : use read_exam, submit_answers and correct_exam.")
    return data


def _show_facts(document: Document) -> None:
    if objects.show_exam_facts(document):
        document.metadata["updated_at"] = vault.format_time(vault.now())


def active(course: str) -> list[Document]:
    """The deliverables of a course in progress : assigned, with check-ins, or waiting for their correction."""
    return [exam for exam in objects.iter_exams(course) if objects.is_deliverable(exam) and objects.exam_status(exam) in objects.ACTIVE_DELIVERABLE]


def _log_project(document: Document, text: str) -> None:
    """A line in the progress log of the project of a deliverable. A missing project note is skipped, with a warning."""
    project = objects.unlink(document.metadata.get("project") or "")
    if project and objects.linked_note("project", project, objects.project_file(project)):
        update_project(project, progress=text)


def create_deliverable(
    course: str,
    title: str,
    pitch: str,
    outcome: str,
    project: str,
    difficulty: Difficulty,
    max_sessions: int,
    milestones: list[Milestone],
    planned: Optional[str] = None,
) -> dict:
    """Creates a deliverable : the milestones of a project that the student builds on their own, over several sessions, with a check-in at each session. It writes the subject in the vault, with a roadmap, and keeps the expected outcomes and the hints hidden. A course has at most one deliverable in progress, which never blocks the classes and quizzes.

    Args:
        course (str): The slug of the course
        title (str): The title of the deliverable
        pitch (str): 2-4 sentences in markdown : what the student builds and why it matters for their project
        outcome (str): What the student will have at the end, worth putting on a resume, e.g. 'A CNN that tells my cats from my dogs, 90 % accurate, documented on GitHub'
        project (str): The slug of the project it builds, among the projects of the course
        difficulty (Difficulty): guided : 4-6 small milestones, detailed criteria. standard : 3-4 milestones. autonomous : 2-3 big milestones, criteria on the result only
        max_sessions (int): The number of sessions with a check-in it may take, 1 to 10. It can be extended once, at a check-in
        milestones (list[Milestone]): The milestones, in order, each with the check-in it is due by
        planned (Optional[str]): The slug of the deliverable step of the plan this is, from get_course_state's `plan.next_steps`. Leave it out only for a deliverable the plan didn't foresee : it is then added to the plan, with a warning. Defaults to None.

    Returns:
        dict: {"slug", "path", "milestones", "max_sessions", "warnings"} : the slug of the deliverable, its path relative to the vault (give it to the student), the number of milestones and of sessions, and the warnings
    """
    course_document = objects.get_course(course)
    title = " ".join((title or "").split())
    if not title:
        raise ToolError("The deliverable needs a non empty `title`.")
    if not (pitch or "").strip() or not (outcome or "").strip():
        raise ToolError("The deliverable needs a `pitch` (what the student builds) and an `outcome` (what they will have at the end, for their resume).")
    projects = objects.course_projects(course_document)
    if project not in projects:
        raise ToolError(f"The course '{course}' doesn't build the project '{project}'. Its projects : {', '.join(projects) or 'none'}. Link it first with edit_course `add_projects`.")
    project_note = objects.get_project(project)
    if difficulty not in deliverables.DIFFICULTIES:
        raise ToolError(f"Unknown difficulty '{difficulty}'. Use one of : {', '.join(deliverables.DIFFICULTIES)}.")
    if not isinstance(max_sessions, int) or isinstance(max_sessions, bool) or not 1 <= max_sessions <= deliverables.MAX_SESSIONS:
        raise ToolError(f"`max_sessions` must be a number of sessions from 1 to {deliverables.MAX_SESSIONS}, not {max_sessions!r}.")
    running = active(course)
    if running:
        other = running[0]
        raise ToolError(
            f"The course already has a deliverable in progress : '{objects.slug(other)}' ({objects.exam_status(other)}). "
            "A course has one deliverable at a time : check in on it (checkin_deliverable) or correct it (correct_deliverable) first."
        )
    vault.check_links(pitch, "pitch")
    vault.check_links(outcome, "outcome")
    public, solutions = deliverables.validate_milestones(milestones, objects.course_skills(course_document), max_sessions)
    for number, milestone in enumerate(public, start=1):
        vault.check_links(milestone["text"], f"the text of milestone {number}")
    skills = list(dict.fromkeys(skill for milestone in public for skill in milestone["skills"]))
    skill_links = {skill: objects.link("skill", skill, objects.skill_file(skill), alias=objects.get_skill(skill).metadata.get("name") or skill) for skill in skills}

    warnings = []
    if planned is not None:
        step = plans.planned_step(course_document, planned, "deliverable")
        missing = [skill for skill in step["skills"] if skill not in skills]
        if missing:
            warnings.append(f"The plan expected this deliverable to evaluate {', '.join(missing)} too : evaluate them later, or update the step with edit_course.")
    else:
        step, warning = plans.add_unplanned(course_document, "deliverable", title, " ".join(pitch.split())[:200], skills)
        warnings.append(warning)
    path = objects.step_file(course, step)
    slug = objects.slug(path)
    label = objects.current_session(course_document)
    moment = vault.format_time(vault.now())
    project_link = objects.link("project", project, objects.project_file(project))
    first = [milestone["title"] for milestone in public if milestone["target_session"] == 1]
    next_goal = f"For check-in 1 : {', '.join(first)}" if first else f"For check-in {min(m['target_session'] for m in public)} : {public[0]['title']}"
    data = {
        "type": "deliverable",
        "difficulty": difficulty,
        "max_sessions": max_sessions,
        "extension": 0,
        "questions": [deliverables.stored(milestone) for milestone in public],
        "checkins": [],
        "hints_given": [],
        "next_goal": next_goal,
        "skills": {},
        "corrected_at": None,
    }
    metadata = {"title": title, "status": "assigned", "session": label, "project": project_link, "skills": [objects.link("skill", skill, objects.skill_file(skill)) for skill in skills]}
    metadata.update({key: value for key, value in deliverables.facts(data)["shown"].items()})
    metadata.update({"mean": None, "started_at": moment, "updated_at": moment})
    alias = objects.link("project", project, objects.project_file(project), alias=project_note.metadata.get("name") or project)
    details = f"*Project : {alias} · Difficulty : {difficulty} · {len(public)} milestones · up to {max_sessions} check-in{'s' if max_sessions > 1 else ''}*"
    document = plans.fill(path, metadata, deliverables.render(title, pitch, outcome, details, public, skill_links, next_goal, max_sessions))
    objects.write_exam_data(slug, data)
    vault.write_json(_solutions_file(slug), solutions)

    link = objects.link("exam", slug, path, alias=title)
    objects.append_to_session(course_document, f"Deliverable {link} assigned ({project_link}, {len(public)} milestones, up to {max_sessions} check-ins)")
    dashboards.render_course(course_document)
    vault.write(course_document)
    _log_project(document, f"Deliverable '{title}' started : {len(public)} milestones, up to {max_sessions} sessions")
    return {"slug": slug, "path": vault.relative(path), "milestones": len(public), "max_sessions": max_sessions, "warnings": warnings}


def read_deliverable(deliverable: str) -> dict:
    """Reads a deliverable : what the student wrote for each milestone (the criteria they ticked, their work), the check-ins so far, and for you only the expected outcomes and the hints. Call it before a check-in and before the correction, then look at the files the student points to.

    Args:
        deliverable (str): The slug of the deliverable

    Returns:
        dict: {"slug", "title", "status", "path", "project", "difficulty", "sessions", "next_goal", "milestones", "checkins", "content"} :
            sessions : {"used", "total", "left", "extended"}, the sessions with a check-in and the budget,
            milestones : [{"milestone", "title", "skills", "format", "target_session", "status", "criteria" ([{"criterion", "done"}]), "work", "expected_outcome", "hints" ([{"hint", "text", "given"}])}] : the expected outcomes and the hints are for you only,
            checkins : [{"checkin", "session", "date"}],
            content : the note of the deliverable
    """
    document = objects.find_document("exams", deliverable)
    data = _data(document)
    milestones = data["questions"]
    solutions = _solutions(deliverable, len(milestones))
    work = deliverables.parse_work(document.body, len(milestones))
    before = dict(document.metadata)
    _show_facts(document)
    if document.metadata != before:
        vault.write(document)
    given = {tuple(pair) for pair in data.get("hints_given") or []}
    used, total = deliverables.sessions_used(data), deliverables.budget(data)
    return {
        "slug": deliverable,
        "title": document.metadata.get("title"),
        "status": objects.exam_status(document),
        "path": vault.relative(document.path),
        "project": objects.unlink(document.metadata.get("project") or "") or None,
        "difficulty": data.get("difficulty"),
        "sessions": {"used": used, "total": total, "left": max(total - used, 0), "extended": bool(data.get("extension"))},
        "next_goal": data.get("next_goal"),
        "milestones": [
            {
                "milestone": number,
                **{key: milestone.get(key) for key in ("title", "skills", "format", "target_session", "status")},
                **found,
                "expected_outcome": solution["expected_outcome"],
                "hints": [{"hint": index, "text": hint, "given": (number, index) in given} for index, hint in enumerate(solution.get("hints") or [], start=1)],
            }
            for number, (milestone, found, solution) in enumerate(zip(milestones, work, solutions), start=1)
        ],
        "checkins": [{"checkin": number, "session": checkin.get("session"), "date": checkin.get("date")} for number, checkin in enumerate(data.get("checkins") or [], start=1)],
        "content": document.body,
    }
