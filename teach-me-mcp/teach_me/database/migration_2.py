"""Migration 2 : the views of version 1 fixed, now that they were checked in Obsidian.

Each step works on every note of the vault and returns one line per note it changed. The steps run in
order, each one on the notes as the previous steps left them.
"""

from __future__ import annotations

from typing import Callable

from teach_me.database import dashboards


def views() -> list[str]:
    """The bases are written again : the Plan view of version 1 didn't parse, and some columns had no name.
    A base the student changed in Obsidian (a sort, a column) is overwritten too : the backup keeps their version."""
    return [f"{path} : written again" for path in dashboards.ensure_bases(force=True)]


STEPS: list[Callable[[], list[str]]] = [views]


def run() -> list[str]:
    changes = []
    for step in STEPS:
        changes += step()
    return changes
