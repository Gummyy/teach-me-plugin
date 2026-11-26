"""Deliverables : the milestones of a project, built by the student on their own over several sessions.

    create_deliverable -> (the student works) -> checkin_deliverable at each session -> correct_deliverable

A course has at most one deliverable in progress : it runs alongside the classes and the quizzes, and never blocks them.
The milestones are graded once, at the end. The check-ins give feedback, hints when needed, and the next goals.
"""

from typing import Optional

from teach_me.database import blocks, dashboards, objects, quiz, vault
from teach_me.database import deliverable as deliverables
from teach_me.database import plan as plans
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.project import update_project
from teach_me.tools.schemas import Difficulty, HintGiven, Milestone, MilestoneCheckin, MilestoneGrade, Reschedule


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


def _roadmap(document: Document, data: dict) -> None:
    """The roadmap of a deliverable written again from its hidden data. The caller writes the note."""
    content = deliverables.roadmap(data["questions"], data.get("next_goal"), deliverables.sessions_used(data), deliverables.budget(data), bool(data.get("corrected_at")))
    document.body = blocks.replace(document.body, deliverables.ROADMAP_BLOCK, content, vault.format_session(vault.now()))


def _milestone_number(value, count: int, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= count:
        raise ToolError(f"{where} : `milestone` must be the number of a milestone, from 1 to {count}, not {value!r}.")
    return value


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


def checkin_deliverable(
    deliverable: str,
    shown: str,
    milestones: list[MilestoneCheckin],
    next_goals: str,
    hints: Optional[list[HintGiven]] = None,
    reschedule: Optional[list[Reschedule]] = None,
    extend: Optional[int] = None,
) -> dict:
    """Records a check-in on a deliverable, once the student showed their work at this session (their files, their repo, a demo : never take "it's done" as a proof). It appends your feedback to the note, the hints you give and the next goals, updates the roadmap, and logs it in the course and the project. Several check-ins in the same session count as one session. Nothing is graded : the milestones are graded at the end, with correct_deliverable.

    Args:
        deliverable (str): The slug of the deliverable
        shown (str): 1-3 sentences : what the student showed you at this session
        milestones (list[MilestoneCheckin]): Where each milestone the student worked on stands, with your feedback. Leave out the milestones not discussed
        next_goals (str): What the student does before the next session, in 1-2 sentences : it shows in the roadmap and in Home.md
        hints (Optional[list[HintGiven]]): The hidden hints you give, when the student is stuck : the tool writes them in the note. Hints never lower the grade. Defaults to None.
        reschedule (Optional[list[Reschedule]]): Milestones now due by another check-in, e.g. when one turned out too big. Defaults to None.
        extend (Optional[int]): More sessions for the deliverable, when the student needs more time and agrees : once at most, up to its `max_sessions`. Defaults to None.

    Returns:
        dict: {"checkin", "status", "sessions", "milestones_done", "next_step"} : the number of the check-in, the status of the deliverable, the sessions {"used", "total", "left"}, the milestones done, and what to do next
    """
    document = objects.find_document("exams", deliverable)
    data = _data(document)
    status = objects.exam_status(document)
    if status not in objects.ACTIVE_DELIVERABLE:
        raise ToolError(f"The deliverable '{deliverable}' is {status} : it takes no more check-ins.")
    course_document = objects.get_course(objects.document_course(document))
    label = objects.current_session(course_document)
    checkins = data.setdefault("checkins", [])
    same_session = bool(checkins) and checkins[-1].get("session") == label
    changes = []
    if extend is not None:
        if data.get("extension"):
            raise ToolError(f"The deliverable '{deliverable}' was already extended once, by {data['extension']} session(s) : grade what exists with correct_deliverable.")
        if not isinstance(extend, int) or isinstance(extend, bool) or not 1 <= extend <= int(data.get("max_sessions") or 1):
            raise ToolError(f"`extend` must be a number of sessions from 1 to {data.get('max_sessions')}, not {extend!r}.")
        data["extension"] = extend
        changes.append(f"{extend} more session{'s' if extend > 1 else ''} : up to {deliverables.budget(data)} check-ins")
    elif status == "submitted" and not same_session:
        raise ToolError(
            f"Every session of the deliverable '{deliverable}' is used ({deliverables.budget(data)}). Grade what exists with correct_deliverable, "
            "or, once at most and if the student agrees, give it more sessions with `extend`."
        )
    if not (shown or "").strip() or not (next_goals or "").strip():
        raise ToolError("A check-in needs `shown` (what the student showed you) and `next_goals` (what they do before the next session).")
    questions = data["questions"]
    if not milestones:
        raise ToolError("Give your feedback on at least one milestone in `milestones` : the ones the student worked on.")
    feedback, seen = [], set()
    for item in milestones:
        number = _milestone_number((item or {}).get("milestone"), len(questions), "A milestone of `milestones`")
        if number in seen:
            raise ToolError(f"Milestone {number} is given twice in `milestones`.")
        seen.add(number)
        if item.get("status") not in deliverables.MILESTONE_STATUSES:
            raise ToolError(f"Milestone {number} needs a `status` among : {', '.join(deliverables.MILESTONE_STATUSES)}.")
        text = str(item.get("feedback") or "").strip()
        if not text:
            raise ToolError(f"Milestone {number} has no `feedback` : say what works and what to improve.")
        vault.check_links(text, f"the feedback on milestone {number}")
        feedback.append((number, item["status"], text))
    solutions = _solutions(deliverable, len(questions))
    given, hint_texts = [list(pair) for pair in data.get("hints_given") or []], []
    for item in hints or []:
        number = _milestone_number((item or {}).get("milestone"), len(questions), "A hint of `hints`")
        available = solutions[number - 1].get("hints") or []
        index = item.get("hint")
        if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= len(available):
            raise ToolError(f"Milestone {number} has {len(available)} hint(s) : `hint` must be from 1 to {len(available)}, not {index!r}." if available else f"Milestone {number} has no hint.")
        hint_texts.append((number, available[index - 1]))
        if [number, index] not in given:
            given.append([number, index])
    for item in reschedule or []:
        number = _milestone_number((item or {}).get("milestone"), len(questions), "A milestone of `reschedule`")
        target = item.get("target_session")
        if not isinstance(target, int) or isinstance(target, bool) or not 1 <= target <= deliverables.budget(data):
            raise ToolError(f"Milestone {number} : `target_session` must be from 1 to {deliverables.budget(data)}, not {target!r}. Extend the deliverable with `extend` first.")
        if target != questions[number - 1]["target_session"]:
            changes.append(f"Milestone {number} · {questions[number - 1]['title']} : due by check-in {questions[number - 1]['target_session']} → {target}")
            questions[number - 1]["target_session"] = target

    for number, milestone_status, _ in feedback:
        questions[number - 1]["status"] = milestone_status
    moment = vault.format_time(vault.now())
    checkins.append({"session": label, "date": moment, "milestones": {str(number): milestone_status for number, milestone_status, _ in feedback}})
    data["hints_given"] = given
    data["next_goal"] = " ".join(next_goals.split())
    objects.write_exam_data(deliverable, data)  # the source of truth first

    number = deliverables.sessions_used(data)
    titles = [(n, questions[n - 1]["title"], milestone_status, text) for n, milestone_status, text in feedback]
    document.body = deliverables.add_checkin(document.body, deliverables.render_checkin(number, label, shown, titles, hint_texts, changes, next_goals))
    _roadmap(document, data)
    _show_facts(document)
    document.metadata["updated_at"] = moment
    vault.write(document)

    facts = deliverables.facts(data)
    done, total, used = facts["shown"]["milestones_done"], deliverables.budget(data), facts["shown"]["sessions"]
    link = objects.link("exam", deliverable, document.path, alias=str(document.metadata.get("title") or deliverable))
    objects.append_to_session(course_document, f"Check-in {number}/{total} on the deliverable {link} : {done}/{len(questions)} milestones done" + (f", {len(hint_texts)} hint(s) given" if hint_texts else ""))
    vault.write(course_document)
    _log_project(document, f"Check-in {number} on '{document.metadata.get('title')}' : {done}/{len(questions)} milestones done")

    if facts["status"] == "submitted":
        step = (
            "Every session of the deliverable is used : grade it now with correct_deliverable (call read_deliverable and look at the work first). "
            + ("If the student needs more time and agrees, you can extend it once instead, with `extend`." if not data.get("extension") else "It was already extended : grade what exists.")
        )
    elif done == len(questions):
        step = "Every milestone is done : grade the deliverable with correct_deliverable (call read_deliverable and look at the work first)."
    else:
        step = f"Next check-in at the next session : {total - used} left. Between the sessions, the student works on their own : remind them of the next goals."
    return {"checkin": number, "status": facts["status"], "sessions": {"used": used, "total": total, "left": max(total - used, 0)}, "milestones_done": done, "next_step": step}


def correct_deliverable(deliverable: str, grades: list[MilestoneGrade], showcase: Optional[str] = None, comments: Optional[dict[str, str]] = None) -> dict:
    """Grades a deliverable, once every session of its budget is used or its work is done : call read_deliverable and look at the work first. It computes the grade of each skill from the milestones graded, and appends the correction to the note.

    A milestone the student didn't work on is `abandoned` : no grade, it counts for no skill. When at least half of the milestones are abandoned, the deliverable is abandoned, without a mean. The hints given never lower a grade.

    Args:
        deliverable (str): The slug of the deliverable
        grades (list[MilestoneGrade]): The grade of every milestone, each with its explanation
        showcase (Optional[str]): What the student built, in one or two sentences they can put on their resume, written with them. Required unless the deliverable is abandoned. Defaults to None.
        comments (Optional[dict[str, str]]): A short comment for each evaluated skill, by slug, shown in the correction and in the history of the skill. Defaults to None.

    Returns:
        dict: {"status", "grades", "mean", "skills", "showcase"} : "corrected" or "abandoned", the grade of each milestone ("abandoned" for those), the mean of the milestones graded (null when abandoned), the grade of each skill in this deliverable ({"grade", "score"}) and the showcase line
    """
    document = objects.find_document("exams", deliverable)
    data = _data(document)
    status = objects.exam_status(document)
    if status not in objects.ACTIVE_DELIVERABLE:
        raise ToolError(f"The deliverable '{deliverable}' is already {status} : a deliverable is graded once.")
    questions = data["questions"]
    given: dict[int, tuple[str, str]] = {}
    for item in grades or []:
        number = _milestone_number((item or {}).get("milestone"), len(questions), "A grade of `grades`")
        if number in given:
            raise ToolError(f"Milestone {number} is graded twice in `grades`.")
        if item.get("grade") not in deliverables.MILESTONE_GRADES:
            raise ToolError(f"Milestone {number} needs a `grade` among : {', '.join(deliverables.MILESTONE_GRADES)}.")
        explanation = str(item.get("explanation") or "").strip()
        if not explanation:
            raise ToolError(f"The grade of milestone {number} has no `explanation`.")
        vault.check_links(explanation, f"the explanation of milestone {number}")
        given[number] = (item["grade"], explanation)
    missing = [number for number in range(1, len(questions) + 1) if number not in given]
    if missing:
        raise ToolError(f"The milestone(s) {', '.join(map(str, missing))} have no grade : grade every milestone, `abandoned` for one the student didn't work on.")
    for number, question in enumerate(questions, start=1):
        grade = given[number][0]
        if grade == deliverables.ABANDONED:
            question["status"], question["grade"] = deliverables.ABANDONED, None
        else:
            question["grade"] = grade
    abandoned = deliverables.is_abandoned(questions)
    showcase = " ".join((showcase or "").split())
    if not showcase and not abandoned:
        raise ToolError("Give the `showcase` : what the student built, in one or two sentences they can put on their resume. Write it with them.")

    graded = [question for question in questions if question.get("grade") in quiz.GRADES]
    skills = quiz.skill_grades(graded, [question["grade"] for question in graded])
    comments = comments or {}
    unknown = [skill for skill in comments if skill not in skills]
    if unknown:
        raise ToolError(f"This deliverable doesn't evaluate : {', '.join(unknown)}. Evaluated skills : {', '.join(skills) or 'none'}.")
    data["skills"] = {skill: {**grade, "comment": comments.get(skill)} for skill, grade in skills.items()}
    moment = vault.now()
    data["corrected_at"] = vault.format_time(moment)
    data["showcase"] = showcase or None
    objects.write_exam_data(deliverable, data)  # the source of truth first : the notes are only views of it

    solutions = _solutions(deliverable, len(questions))
    names = {skill: (note.metadata.get("name") if note else None) or skill for skill, note in ((skill, objects.linked_note("skill", skill, objects.skill_file(skill))) for skill in skills)}
    skill_links = {skill: objects.link_or_name("skill", skill, objects.skill_file(skill), alias=names[skill]) for skill in skills}
    explanations = [given[number][1] for number in range(1, len(questions) + 1)]
    correction = deliverables.render_correction(vault.format_session(moment), questions, solutions, explanations, data["showcase"], data["skills"], skill_links)
    _roadmap(document, data)
    _show_facts(document)
    document.body = f"{document.body.rstrip()}\n\n{correction}"
    vault.write(document)
    course_document = objects.get_course(objects.document_course(document))
    objects.refresh_skills(objects.unlink(course_document.metadata.get("user", "")), skills)

    facts = deliverables.facts(data)
    title = str(document.metadata.get("title") or deliverable)
    link = objects.link("exam", deliverable, document.path, alias=title)
    counts = ", ".join(f"{sum(q.get('grade') == grade for q in questions)} {grade}" for grade in quiz.GRADES if any(q.get("grade") == grade for q in questions))
    dropped = sum(q.get("status") == deliverables.ABANDONED for q in questions)
    summary = ", ".join(part for part in (counts, f"{dropped} abandoned" if dropped else "") if part)
    objects.append_to_session(course_document, f"Deliverable {link} {facts['status']} : {summary}" + (f" (mean {facts['mean']}/5)" if facts["mean"] is not None else ""))
    dashboards.render_course(course_document)
    vault.write(course_document)
    _log_project(document, f"Deliverable '{title}' {facts['status']}" + (f" : {showcase}" if showcase else ""))
    return {
        "status": facts["status"],
        "grades": [question.get("grade") or deliverables.ABANDONED for question in questions],
        "mean": facts["mean"],
        "skills": skills,
        "showcase": data["showcase"],
    }
