"""Report card of a course, for the chat. The course note shows the same, always up to date, with Obsidian bases."""

from teach_me.database import objects, quiz, vault


def _cell(value) -> str:
    """Escapes a value for a markdown table cell."""
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def report_card(course: str) -> str:
    """The report card of a course, from its skills and exams : skills of the course, grade and progression of each skill (from the exams of all the courses that evaluate it), list of the exams of the course. The course note shows it too, always up to date : no need to call this tool for the vault.

    Args:
        course (str): The slug of the course

    Returns:
        str: The report card, in markdown, to share in the chat
    """
    document = objects.get_course(course)
    metadata = document.metadata
    grades = objects.skill_grades(objects.unlink(metadata.get("user", "")))
    skills = [objects.get_skill(skill) for skill in objects.course_skills(document)]
    scores = [grades[objects.slug(skill)]["score"] for skill in skills if objects.slug(skill) in grades]

    lines = [f"# 🎓 Report card : {metadata.get('name') or course}", "", _cell(metadata.get("subject")), ""]
    if scores:
        average = round(sum(scores) / len(scores), 2)
        lines.append(f"**{len(scores)}/{len(skills)}** skills evaluated, average grade : **{quiz.grade_of(average)}** ({average}/5)")
    else:
        lines.append(f"**0/{len(skills)}** skills evaluated : take an exam to start filling this report card !")
    lines += ["", "## Skills", "", "| Skill | Description | Grade | Progression |", "| --- | --- | --- | --- |"]
    for skill in skills:
        name = objects.slug(skill)
        link = objects.link("skill", name, skill.path, alias=skill.metadata.get("name") or name)
        grade = grades.get(name)
        lines.append(
            f"| {_cell(link)} | {_cell(skill.metadata.get('description'))} | "
            + (f"{grade['grade']} ({grade['score']}/5) | {' → '.join(grade['history'])} |" if grade else "— | not evaluated yet |")
        )

    lines += ["", "## Exams", ""]
    exams = list(objects.iter_exams(course))
    if exams:
        lines += ["| Date | Exam | Type | Status |", "| --- | --- | --- | --- |"]
        for exam in exams:
            created = vault.parse_time(exam.metadata.get("created_at"))
            link = objects.link("exam", objects.slug(exam), exam.path, alias=exam.metadata.get("title") or objects.slug(exam))
            lines.append(
                f"| {f'{created:%Y-%m-%d}' if created else ''} | {_cell(link)} | "
                f"{objects.exam_type(exam)} | {_cell(exam.metadata.get('status'))} |"
            )
    else:
        lines.append("No exam yet.")

    return "\n".join(lines)
