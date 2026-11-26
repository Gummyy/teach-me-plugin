"""Migration 4 : every note of the tools gets a stable `id`, its file name, so that a note renamed or moved in Obsidian can be put back.

A note that isn't where the tools expect it (renamed before it had an id) gets no id : the tools can't tell which note it was.
"""

from __future__ import annotations

from teach_me.database import renames


def run() -> list[str]:
    return renames.restore()
