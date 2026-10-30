"""Creating, listing and editing the skills of a user.

A skill is a note of its own (skills/<skill>.md) owned by a user. Several courses of that user can
evaluate the same skill : its marks come from the exams of all of them.
"""

from typing import Optional

from teach_me.database import objects, vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools.schemas import SkillDeclaration
from teach_me.tools.users import _validate_skills


def _summary(document: Document, grades: dict[str, dict]) -> dict:
    return {
        "slug": objects.slug(document),
        "name": document.metadata.get("name"),
        "description": document.body,
        **{key: (grades.get(objects.slug(document)) or {}).get(key) for key in ("grade", "score")},
    }


def check_skills(user: str, skills: list[str]) -> list[str]:
    """Checks that the skills exist and belong to the user. Returns their slugs, without duplicates."""
    slugs = list(dict.fromkeys(objects.unlink(skill) for skill in skills))
    for skill in slugs:
        owner = objects.unlink(objects.get_skill(skill).metadata.get("user", ""))
        if owner != user:
            raise ToolError(f"The skill '{skill}' belongs to '{owner}', not to '{user}'.")
    return slugs


def create_skills(user: str, skills: list[SkillDeclaration]) -> list[dict]:
    """Creates the skills of a user, before the course that evaluates them. A skill whose name the user already has is reused, not duplicated : its description is kept (change it with edit_skill).

    Args:
        user (str): The slug of the user
        skills (list[SkillDeclaration]): The skills to create

    Returns:
        list[dict]: One item per skill, in order : {"slug", "name", "reused"}. Give the slugs to create_course and to the questions of the exams.
    """
    objects.get_user(user)
    if not skills:
        raise ToolError("Give at least one skill in `skills`.")
    existing = {str(document.metadata.get("name") or "").lower(): document for document in objects.iter_skills(user)}
    moment = vault.format_time(vault.now())
    user_link = objects.link("user", user, objects.user_file(user))
    created = []
    for skill in _validate_skills(skills, "skills"):
        known = existing.get(skill["name"].lower())
        if known is not None:
            created.append({"slug": objects.slug(known), "name": known.metadata.get("name"), "reused": True})
            continue
        slug = vault.unique_slug(vault.slugify(skill["name"]), lambda s: objects.skill_file(s).exists())
        vault.write(
            Document(
                objects.skill_file(slug),
                {"name": skill["name"], "user": user_link, "created_at": moment},
                skill["description"],
            )
        )
        created.append({"slug": slug, "name": skill["name"], "reused": False})
    return created


def list_skills(user: str, course: Optional[str] = None) -> list[dict]:
    """Lists the skills of a user, or only the ones a course evaluates, with their grade (from the exams of all the courses).

    Args:
        user (str): The slug of the user
        course (Optional[str]): The slug of a course, to list only its skills, in the order of the course. Defaults to None.

    Returns:
        list[dict]: One item per skill : {"slug", "name", "description", "grade", "score"}. The score is the weighted mean of the grades of its questions (A 5, B 4, C 2, D 1, E 0, a project exam weighing twice a quiz), the grade the closest letter. Both are null for a skill not evaluated yet.
    """
    objects.get_user(user)
    grades = objects.skill_grades(user)
    if course is None:
        return [_summary(document, grades) for document in objects.iter_skills(user)]
    document = objects.get_course(course)
    owner = objects.unlink(document.metadata.get("user", ""))
    if owner != user:
        raise ToolError(f"The course '{course}' belongs to '{owner}', not to '{user}'.")
    return [_summary(objects.get_skill(skill), grades) for skill in objects.course_skills(document)]


def edit_skill(skill: str, name: Optional[str] = None, description: Optional[str] = None) -> dict:
    """Renames a skill or changes its description. Its slug doesn't change, so the courses and the exams that use it are kept.

    Args:
        skill (str): The slug of the skill
        name (Optional[str]): The new name of the skill. Defaults to None.
        description (Optional[str]): The new description : one sentence about what the student can do once the skill is validated. Defaults to None.

    Returns:
        dict: {"slug", "name", "description", "grade", "score"} : the skill after the update
    """
    document = objects.get_skill(skill)
    if name is None and description is None:
        raise ToolError("Nothing to update : give a new `name` or a new `description`.")
    user = objects.unlink(document.metadata.get("user", ""))
    if name is not None:
        name = name.strip()
        if not name:
            raise ToolError("The skill `name` can't be empty.")
        for other in objects.iter_skills(user):
            if objects.slug(other) != skill and str(other.metadata.get("name") or "").lower() == name.lower():
                raise ToolError(f"'{user}' already has a skill named '{name}' : '{objects.slug(other)}'.")
        document.metadata["name"] = name
    if description is not None:
        document.body = description.strip()
    document.metadata["updated_at"] = vault.format_time(vault.now())
    vault.write(document)
    return _summary(document, objects.skill_grades(user))
