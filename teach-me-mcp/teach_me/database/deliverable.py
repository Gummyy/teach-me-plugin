"""Deliverables : the milestones of a project, built by the student on their own over several sessions.

A deliverable is an exam of its own kind. Its questions are milestones : big pieces of the project, each with
criteria the student checks their work against, an expected outcome and hints kept hidden. The student works
between the sessions, in their project and in the note of the deliverable. At each session, they show where they
are : the teacher checks in (feedback, hints when needed, next goals). Once the sessions of its budget are used,
or the work is done, the teacher grades each milestone.

    # Title

    The pitch

    > [!example] 🎯 What you will have at the end
    > The line for the resume

    %% teach-me:roadmap start %%          <- generated : rewritten at each check-in
    ## 🗺️ Roadmap
    | # | Milestone | Target | Status |
    %% teach-me:roadmap end 3fa2c1d0 %%

    ## 🏁 Milestone 1 · Title
    *Skills : [[skill-x|x]] · Format : code · Target : check-in 1*

    What to build

    - [ ] A criterion                    <- ticked by the student

    **Your work :**

    What the student did, links to their files

    ## 📅 Check-ins                       <- appended by checkin_deliverable, never rewritten
    ### Check-in 1 · 2026-11-26 14:00

    ## ✅ Correction (2026-12-02 18:00)   <- appended by correct_deliverable, never rewritten

The hidden data (`.teach-me/exams/<deliverable>.json`) holds the milestones as `questions` (kind "milestone"),
so that the grades of the skills count them as any question, and the check-ins. The expected outcomes and the
hints are in `.teach-me/solutions/<deliverable>.json`.

Only pure functions here : no file access.
"""

from __future__ import annotations

import re
from typing import Optional

from teach_me.database import blocks, quiz
from teach_me.errors import ToolError

DIFFICULTIES = ("guided", "standard", "autonomous")
MILESTONE_STATUSES = ("to do", "in progress", "done")
ABANDONED = "abandoned"
"""The grade of a milestone the student didn't work on : it gets no grade, and counts for no skill."""
MILESTONE_GRADES = ("A", "B", "C", "D", ABANDONED)
MAX_SESSIONS = 10
MAX_MILESTONES = 8
ROADMAP_BLOCK = "roadmap"
WORK_MARKER = "**Your work :**"
CHECKINS_HEADING = "## 📅 Check-ins"
STATUS_ICONS = {"to do": "⏳ to do", "in progress": "🔨 in progress", "done": "✅ done", ABANDONED: "🏳️ abandoned"}

_MILESTONE_HEADING = re.compile(r"^## 🏁 Milestone (\d+)\b.*$", re.MULTILINE)
_END = re.compile(rf"^(?:## 🏁 Milestone \d+|{re.escape(CHECKINS_HEADING)}|## ✅ Correction|{re.escape(blocks.NOTES_HEADING)}|%% teach-me:)", re.MULTILINE)
_CRITERION = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*?)\s*$", re.MULTILINE)


# --------------------------------------------------------------------------- #
# Milestones
# --------------------------------------------------------------------------- #


def _texts(value) -> list[str]:
    items = [value] if isinstance(value, str) else list(value or [])
    return [" ".join(str(item).split()) for item in items if str(item).strip()]


def validate_milestones(milestones: list, declared_skills: list[str], max_sessions: int) -> tuple[list[dict], list[dict]]:
    """Checks the milestones sent by the model. Returns their public part (stored in the hidden data, shown in the note) and their solutions (hidden)."""
    if not milestones:
        raise ToolError("A deliverable needs at least one milestone in `milestones`.")
    if len(milestones) > MAX_MILESTONES:
        raise ToolError(f"A deliverable has at most {MAX_MILESTONES} milestones, not {len(milestones)} : split the project into several deliverables.")
    public, solutions = [], []
    for number, milestone in enumerate(milestones, start=1):
        where = f"Milestone {number}"
        if not isinstance(milestone, dict):
            raise ToolError(f"{where} must be an object with 'title', 'text', 'skills', 'format', 'criteria', 'expected_outcome' and 'target_session'.")
        title = " ".join(str(milestone.get("title") or "").split())
        text = str(milestone.get("text") or "").strip()
        if not title or not text:
            raise ToolError(f"{where} needs a `title` and a `text` : what to build.")
        skills = list(dict.fromkeys(_texts(milestone.get("skills"))))
        if not skills:
            raise ToolError(f"{where} is associated with no skills. Associate it with at least one skill among : {', '.join(declared_skills)}")
        unknown = [skill for skill in skills if skill not in declared_skills]
        if unknown:
            raise ToolError(f"{where} evaluates {', '.join(unknown)}, which the course doesn't declare. Declared skills : {', '.join(declared_skills)}.")
        criteria = _texts(milestone.get("criteria"))
        if not criteria:
            raise ToolError(f"{where} needs `criteria` : the checklist the student checks their work against, while they work alone.")
        expected = str(milestone.get("expected_outcome") or "").strip()
        if not expected:
            raise ToolError(f"{where} needs its `expected_outcome`, so that it can be corrected later.")
        target = milestone.get("target_session")
        if not isinstance(target, int) or isinstance(target, bool) or not 1 <= target <= max_sessions:
            raise ToolError(f"{where} : `target_session` must be the check-in by which it should be done, from 1 to {max_sessions} (`max_sessions`), not {target!r}.")
        public.append(
            {
                "kind": "milestone",
                "skills": skills,
                "title": title,
                "text": text,
                "format": " ".join(str(milestone.get("format") or "").split()) or None,
                "criteria": criteria,
                "target_session": target,
                "status": "to do",
            }
        )
        solutions.append({"expected_outcome": expected, "hints": [str(hint).strip() for hint in milestone.get("hints") or [] if str(hint).strip()]})
    return public, solutions


def stored(milestone: dict) -> dict:
    """What the hidden data keeps of a milestone : the text and the criteria are in the note."""
    return {key: milestone[key] for key in ("kind", "skills", "title", "format", "target_session", "status") if milestone.get(key) is not None}


# --------------------------------------------------------------------------- #
# Sessions and status
# --------------------------------------------------------------------------- #


def sessions_used(data: dict) -> int:
    """The number of sessions with a check-in : several check-ins in the same session count once."""
    return len(dict.fromkeys(checkin.get("session") for checkin in data.get("checkins") or []))


def budget(data: dict) -> int:
    """The number of sessions of the deliverable, with its extension."""
    return int(data.get("max_sessions") or 1) + int(data.get("extension") or 0)


def is_abandoned(milestones: list[dict]) -> bool:
    """A deliverable is abandoned when at least half of its milestones were."""
    return 2 * sum(milestone.get("status") == ABANDONED for milestone in milestones) >= len(milestones)


def facts(data: dict) -> dict:
    """What the hidden data of a deliverable says : {"status", "mean", "shown"}, `shown` being the other properties of its note."""
    milestones = data.get("questions") or []
    used, checkins = sessions_used(data), data.get("checkins") or []
    mean = None
    if data.get("corrected_at"):
        graded = [milestone["grade"] for milestone in milestones if milestone.get("grade") in quiz.GRADES]
        status = ABANDONED if is_abandoned(milestones) else "corrected"
        if status == "corrected" and graded:
            mean = quiz.mean_score(graded)
    else:
        status = "assigned" if used == 0 else "submitted" if used >= budget(data) else "in progress"
    return {
        "status": status,
        "mean": mean,
        "shown": {
            "difficulty": data.get("difficulty"),
            "milestones": len(milestones),
            "milestones_done": sum(milestone.get("status") == "done" for milestone in milestones),
            "sessions": used,
            "max_sessions": budget(data),
            "next_goal": data.get("next_goal") or None,
            "last_checkin": checkins[-1].get("date") if checkins else None,
            "showcase": data.get("showcase") or None,
        },
    }


# --------------------------------------------------------------------------- #
# The note
# --------------------------------------------------------------------------- #


def _cell(value) -> str:
    return " ".join(str(value if value is not None else "").replace("|", "\\|").split())


def roadmap(milestones: list[dict], next_goal: Optional[str], used: int, total: int) -> str:
    """The roadmap of a deliverable : each milestone, the check-in it is due by, its status, and the next goal."""
    lines = ["## 🗺️ Roadmap", "", f"Check-ins : **{used}/{total}**", "", "| # | Milestone | Due by | Status |", "| --- | --- | --- | --- |"]
    for number, milestone in enumerate(milestones, start=1):
        lines.append(f"| {number} | {_cell(milestone['title'])} | check-in {milestone['target_session']} | {STATUS_ICONS.get(milestone.get('status'), _cell(milestone.get('status')))} |")
    if next_goal:
        lines += ["", f"**Next goal :** {' '.join(next_goal.split())}"]
    return "\n".join(lines)


def render(title: str, pitch: str, outcome: str, details: str, milestones: list[dict], skill_links: dict[str, str], next_goal: str, total: int) -> str:
    """The note of a new deliverable."""
    how = (
        "*How it works : build the milestones on your own, between the sessions. Tick each criterion once your work meets it, "
        "and write under \"Your work\" what you did : links to your files or commits, screenshots, what blocked you. "
        "At each session, show your teacher where you are : they give you feedback, and hints when you need them. "
        "The milestones are graded at the end, once your work is done.*"
    )
    quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in outcome.strip().splitlines())
    parts = [f"# {title}", pitch.strip(), f"> [!example] 🎯 What you will have at the end\n{quoted}", details, how]
    parts.append(blocks.render(ROADMAP_BLOCK, roadmap(milestones, next_goal, 0, total)))
    for number, milestone in enumerate(milestones, start=1):
        skills = ", ".join(skill_links[skill] for skill in milestone["skills"])
        about = [f"{'Skills' if len(milestone['skills']) > 1 else 'Skill'} : {skills}"]
        if milestone.get("format"):
            about.append(f"Format : {milestone['format']}")
        about.append(f"Due by check-in {milestone['target_session']}")
        criteria = "\n".join(f"- [ ] {criterion}" for criterion in milestone["criteria"])
        parts.append(f"## 🏁 Milestone {number} · {milestone['title']}\n*{' · '.join(about)}*\n\n{milestone['text']}\n\n{criteria}\n\n{WORK_MARKER}\n")
    return "\n\n".join(part.strip("\n") for part in parts if part.strip()) + "\n"


def parse_work(body: str, count: int) -> list[dict]:
    """What the student wrote for each milestone : {"criteria": [{"criterion", "done"}], "work"}, `work` being None when they wrote nothing."""
    headings = list(_MILESTONE_HEADING.finditer(body))
    sections: dict[int, str] = {}
    for match in headings:
        end = _END.search(body, match.end())
        sections[int(match.group(1))] = body[match.end(): end.start() if end else len(body)]
    found = []
    for number in range(1, count + 1):
        before, marker, work = sections.get(number, "").partition(WORK_MARKER)
        criteria = [{"criterion": text, "done": box in "xX"} for box, text in _CRITERION.findall(before)]
        found.append({"criteria": criteria, "work": (work.strip() or None) if marker else None})
    return found


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.strip().splitlines())


def render_checkin(number: int, label: str, shown: str, feedback: list[tuple[int, str, str, str]], hints: list[tuple[int, str]], changes: list[str], next_goals: str) -> str:
    """One check-in : what the student showed, the feedback on each milestone, the hints given, the changes to the roadmap and the next goals.

    `feedback` holds (milestone, title, status, feedback), `hints` (milestone, hint)."""
    parts = [f"### Check-in {number} · {label}", f"**What you showed :** {shown.strip()}"]
    for milestone, title, status, text in feedback:
        parts.append(f"> [!note] Milestone {milestone} · {title} : {STATUS_ICONS.get(status, status)}\n{_quote(text)}")
    for milestone, hint in hints:
        parts.append(f"> [!tip] Hint for milestone {milestone}\n{_quote(hint)}")
    if changes:
        parts.append("**Roadmap changed :**\n" + "\n".join(f"- {change}" for change in changes))
    parts.append(f"**Next goals :** {next_goals.strip()}")
    return "\n\n".join(parts)


def add_checkin(body: str, checkin: str) -> str:
    """The body of a deliverable with a check-in appended to its "Check-ins" section, created before the correction and the "My notes" section."""
    start = re.search(rf"^{re.escape(CHECKINS_HEADING)}[ \t]*$", body, re.MULTILINE)
    if start is None:
        stop = re.search(rf"^(?:## ✅ Correction|{re.escape(blocks.NOTES_HEADING)})", body, re.MULTILINE)
        at = stop.start() if stop else len(body)
        return f"{body[:at].rstrip()}\n\n{CHECKINS_HEADING}\n\n{checkin}\n" + (f"\n{body[at:]}" if body[at:].strip() else "")
    following = re.search(r"^## ", body[start.end():], re.MULTILINE)
    at = start.end() + following.start() if following else len(body)
    return f"{body[:at].rstrip()}\n\n{checkin}\n" + (f"\n{body[at:]}" if body[at:].strip() else "")


def render_correction(
    label: str, milestones: list[dict], solutions: list[dict], explanations: list[str], showcase: Optional[str], skills: dict[str, dict], skill_links: dict[str, str]
) -> str:
    """The correction appended to a deliverable : the grades, the grade of each skill, then each milestone."""
    grades = [milestone.get("grade") for milestone in milestones]
    graded = [grade for grade in grades if grade in quiz.GRADES]
    counts = [f"**{graded.count(grade)}** {grade}" for grade in quiz.GRADES if grade in graded]
    if ABANDONED in [milestone.get("status") for milestone in milestones]:
        counts.append(f"**{sum(milestone.get('status') == ABANDONED for milestone in milestones)}** abandoned")
    summary = ", ".join(counts)
    if is_abandoned(milestones):
        summary += " · the deliverable is **abandoned** : at least half of its milestones were. The milestones you built still count for their skills."
    elif graded:
        summary += f" · mean **{quiz.mean_score(graded)}/5**"
    parts = [f"## ✅ Correction ({label})", summary]
    if showcase:
        parts.append(f"> [!example] 🎓 For your resume\n{_quote(showcase)}")
    if skills:
        rows = ["| Skill | Grade | Score | Comment |", "| --- | --- | --- | --- |"]
        for skill, evaluation in skills.items():
            rows.append(f"| {skill_links[skill].replace('|', chr(92) + '|')} | {evaluation['grade']} | {evaluation['score']}/5 | {_cell(evaluation.get('comment'))} |")
        parts.append("\n".join(rows))
    for number, (milestone, solution, explanation) in enumerate(zip(milestones, solutions, explanations), start=1):
        if milestone.get("status") == ABANDONED:
            title, callout = f"Milestone {number} · {milestone['title']} : abandoned, not graded", "Abstract"
        else:
            grade = milestone["grade"]
            title, callout = f"Milestone {number} · {milestone['title']} : {grade} · {quiz.GRADES[grade]['description']}", quiz.CALLOUTS[grade]
        details = f"**Expected :**\n\n{solution['expected_outcome']}\n\n{explanation}"
        parts.append(f"> [!{callout}] {title}\n{_quote(details)}")
    return "\n\n".join(parts)
