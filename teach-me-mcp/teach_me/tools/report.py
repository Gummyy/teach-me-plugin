"""Report card, generated from the course and its exams."""

from teach_me.database import objects, vault
from teach_me.database.vault import Document


def _cell(value) -> str:
    """Escapes a value for a markdown table cell."""
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def report_card(course: str) -> str:
    """Regenerates the report card of a course from its skills and exams : declared skills, latest mark and progression of each skill, list of exams.

    Args:
        course (str): The slug of the course

    Returns:
        str: The report card, in markdown. It is also written to `courses/<course>/report_card.md`.
    """
    document = objects.get_course(course)
    metadata = document.metadata
    history = objects.mark_history(course)
    skills = [skill for skill in metadata.get("skills") or [] if isinstance(skill, dict)]
    latest = [history[str(skill.get("name"))][-1] for skill in skills if history.get(str(skill.get("name")))]

    lines = [f"# 🎓 Report card : {metadata.get('name') or course}", "", _cell(metadata.get("subject")), ""]
    if latest:
        lines.append(
            f"**{len(latest)}/{len(skills)}** skills evaluated, average of the latest marks : "
            f"**{round(sum(latest) / len(latest))}/100**"
        )
    else:
        lines.append(f"**0/{len(skills)}** skills evaluated : take an exam to start filling this report card !")
    lines += ["", "## Skills", "", "| Skill | Description | Latest mark | Progression |", "| --- | --- | --- | --- |"]
    for skill in skills:
        marks = history.get(str(skill.get("name")), [])
        lines.append(
            f"| {_cell(skill.get('name'))} | {_cell(skill.get('description'))} | "
            f"{marks[-1] if marks else '—'} | {' → '.join(map(str, marks)) if marks else 'not evaluated yet'} |"
        )

    lines += ["", "## Exams", ""]
    exams = list(objects.iter_exams(course))
    if exams:
        lines += ["| Date | Exam | Type | Status |", "| --- | --- | --- | --- |"]
        for exam in exams:
            created = vault.parse_time(exam.metadata.get("created_at"))
            title = _cell(exam.metadata.get("title") or exam.slug)
            lines.append(
                f"| {created:%Y-%m-%d} | [[{exam.slug}\\|{title}]] | "
                f"{_cell(exam.metadata.get('type'))} | {_cell(exam.metadata.get('status'))} |"
                if created
                else f"| | [[{exam.slug}\\|{title}]] | {_cell(exam.metadata.get('type'))} | {_cell(exam.metadata.get('status'))} |"
            )
    else:
        lines.append("No exam yet.")

    content = "\n".join(lines)
    vault.write(
        Document(
            objects.courses_dir() / course / "report_card.md",
            {"course": vault.link(f"courses/{course}/course"), "generated_at": vault.format_time(vault.now())},
            content,
        )
    )
    return content
