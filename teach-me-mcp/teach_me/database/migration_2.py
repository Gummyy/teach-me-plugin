"""Migration 2 : the views of version 1 fixed, now that they were checked in Obsidian, the user notes flat,
and the project notes showing their courses and skills.

Each step works on every note of the vault and returns one line per note it changed. The steps run in
order, each one on the notes as the previous steps left them.
"""

from __future__ import annotations

from typing import Callable

from teach_me.database import dashboards, objects, vault


def views() -> list[str]:
    """The bases are written again : the Plan view of version 1 didn't parse, and some columns had no name.
    A base the student changed in Obsidian (a sort, a column) is overwritten too : the backup keeps their version."""
    changed = [f"{path} : written again" for path in dashboards.ensure_bases(force=True)]
    if dashboards.home_file().is_file():
        before = dashboards.home_file().read_text(encoding="utf-8")
        dashboards.ensure_home()
        if dashboards.home_file().read_text(encoding="utf-8") != before:
            changed.append("Home.md : views")
    return changed


def flat_users() -> list[str]:
    """The preferences of a user note become properties of their own, those of an interface prefixed by its name,
    and its known skills a list of texts : {"preferences": {"language": "french"}} -> {"language": "french"}."""
    changed = []
    for document in objects.iter_users():
        metadata = document.metadata
        nested = metadata.get("preferences"), metadata.get("interface_preferences")
        if not any(isinstance(value, dict) for value in nested) and not any(isinstance(skill, dict) for skill in metadata.get("known_skills") or []):
            continue
        general = {key: str(value) for key, value in (nested[0] or {}).items() if value is not None}
        interfaces = {
            interface: {key: str(value) for key, value in (values or {}).items() if value is not None}
            for interface, values in (nested[1] or {}).items()
            if interface in objects.INTERFACES and isinstance(values, dict)
        }
        skills = objects.read_known_skills(metadata)
        rest = {key: value for key, value in metadata.items() if key not in ("preferences", "interface_preferences")}
        document.metadata = objects.write_preferences({**rest, "known_skills": objects.write_known_skills(skills)}, general, interfaces)
        vault.write(document)
        changed.append(f"{vault.relative(document.path)} : preferences and known skills flat")
    return changed


def project_notes() -> list[str]:
    """A project note starts with the views of its courses and their skills, and gets a "My notes" section."""
    changed = []
    for document in objects.iter_projects(None):
        before = document.body
        objects.write_project(document, *objects.split_project(document.body))
        if document.body != before:
            changed.append(f"{vault.relative(document.path)} : views of its courses and skills")
    return changed


STEPS: list[Callable[[], list[str]]] = [views, flat_users, project_notes]


def run() -> list[str]:
    changes = []
    for step in STEPS:
        changes += step()
    return changes
