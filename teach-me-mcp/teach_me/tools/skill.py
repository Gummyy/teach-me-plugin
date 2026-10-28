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


def _summary(document: Document, history: dict[str, list[int]]) -> dict:
    return {
        "slug": document.slug,
        "name": document.metadata.get("name"),
        "description": document.body,
        "latest_mark": (history.get(document.slug) or [None])[-1],
    }


def check_skills(user: str, skills: list[str]) -> list[str]:
    """Checks that the skills exist and belong to the user. Returns their slugs, without duplicates."""
    slugs = list(dict.fromkeys(vault.unlink(skill) for skill in skills))
    for skill in slugs:
        owner = vault.unlink(objects.get_skill(skill).metadata.get("user", ""))
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
    created = []
    for skill in _validate_skills(skills, "skills"):
        known = existing.get(skill["name"].lower())
        if known is not None:
            created.append({"slug": known.slug, "name": known.metadata.get("name"), "reused": True})
            continue
        slug = vault.unique_slug(vault.slugify(skill["name"]), lambda s: (objects.skills_dir() / f"{s}.md").exists())
        vault.write(
            Document(
                objects.skills_dir() / f"{slug}.md",
                {"name": skill["name"], "user": vault.link(user), "created_at": moment},
                skill["description"],
            )
        )
        created.append({"slug": slug, "name": skill["name"], "reused": False})
    return created


def list_skills(user: str, course: Optional[str] = None) -> list[dict]:
    """Lists the skills of a user, or only the ones a course evaluates, with their latest mark (from the exams of all the courses).

    Args:
        user (str): The slug of the user
        course (Optional[str]): The slug of a course, to list only its skills, in the order of the course. Defaults to None.

    Returns:
        list[dict]: One item per skill : {"slug", "name", "description", "latest_mark"}
    """
    objects.get_user(user)
    history = objects.mark_history(user)
    if course is None:
        return [_summary(document, history) for document in objects.iter_skills(user)]
    document = objects.get_course(course)
    owner = vault.unlink(document.metadata.get("user", ""))
    if owner != user:
        raise ToolError(f"The course '{course}' belongs to '{owner}', not to '{user}'.")
    return [_summary(objects.get_skill(skill), history) for skill in objects.course_skills(document)]


def edit_skill(skill: str, name: Optional[str] = None, description: Optional[str] = None) -> dict:
    """Renames a skill or changes its description. Its slug doesn't change, so the courses and the exams that use it are kept.

    Args:
        skill (str): The slug of the skill
        name (Optional[str]): The new name of the skill. Defaults to None.
        description (Optional[str]): The new description : one sentence about what the student can do once the skill is validated. Defaults to None.

    Returns:
        dict: {"slug", "name", "description", "latest_mark"} : the skill after the update
    """
    document = objects.get_skill(skill)
    if name is None and description is None:
        raise ToolError("Nothing to update : give a new `name` or a new `description`.")
    user = vault.unlink(document.metadata.get("user", ""))
    if name is not None:
        name = name.strip()
        if not name:
            raise ToolError("The skill `name` can't be empty.")
        for other in objects.iter_skills(user):
            if other.slug != skill and str(other.metadata.get("name") or "").lower() == name.lower():
                raise ToolError(f"'{user}' already has a skill named '{name}' : '{other.slug}'.")
        document.metadata["name"] = name
    if description is not None:
        document.body = description.strip()
    document.metadata["updated_at"] = vault.format_time(vault.now())
    vault.write(document)
    return _summary(document, objects.mark_history(user))
