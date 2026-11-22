"""The parts of a note the tools generate, and the student's own notes next to them.

A generated block sits between two Obsidian comments, hidden in reading view. The end marker holds a
hash of what the tools wrote :

    %% teach-me:history start %%
    ...
    %% teach-me:history end 3fa2c1d0 %%

The tools rewrite the block whenever its data changes. When the student edited it in the meantime (its
content doesn't match the hash anymore), their version isn't lost : it moves to the "My notes" section
of the note, in a folded callout, before the block is rewritten. Everything outside the blocks belongs
to the student and is never rewritten.

Only pure functions here : no file access.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

NOTES_HEADING = "## ✏️ My notes"
"""The section of a note that belongs to the student : the tools only add to it, never rewrite it."""
_SESSION = re.compile(r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2}[ \t]*$", re.MULTILINE)
"""The first session of a course log : the notes of a course come before its log."""


def _hash(content: str) -> str:
    return hashlib.sha1(content.strip().encode("utf-8")).hexdigest()[:8]


def _pattern(name: str) -> re.Pattern:
    return re.compile(
        rf"^%% teach-me:{re.escape(name)} start %%[ \t]*\n(?P<content>.*?)^%% teach-me:{re.escape(name)} end (?P<hash>[0-9a-f]*) ?%%[ \t]*$",
        re.DOTALL | re.MULTILINE,
    )


def _markers(name: str) -> re.Pattern:
    return re.compile(rf"^%% teach-me:{re.escape(name)} (start|end)[^\n]*%%[ \t]*\n?", re.MULTILINE)


def render(name: str, content: str) -> str:
    content = content.strip("\n")
    return f"%% teach-me:{name} start %%\n{content}\n%% teach-me:{name} end {_hash(content)} %%"


def content(body: str, name: str) -> Optional[str]:
    """What the block holds now, or None when the note has no such block."""
    match = _pattern(name).search(body)
    return match.group("content").strip("\n") if match else None


def notes_bounds(body: str) -> Optional[tuple[int, int]]:
    """Start and end of the "My notes" section, heading included, or None."""
    match = re.search(rf"^{re.escape(NOTES_HEADING)}[ \t]*$", body, re.MULTILINE)
    if match is None:
        return None
    following = re.search(r"^## ", body[match.end():], re.MULTILINE)
    return match.start(), match.end() + following.start() if following else len(body)


def notes(body: str) -> str:
    """The text the student wrote in their "My notes" section."""
    bounds = notes_bounds(body)
    return body[bounds[0] + len(NOTES_HEADING):bounds[1]].strip() if bounds else ""


def ensure_notes(body: str) -> str:
    """Adds an empty "My notes" section when the note has none : before the session log of a course, at the end of any other note."""
    if notes_bounds(body) is not None:
        return body
    session = _SESSION.search(body)
    if session is None:
        return f"{body.rstrip()}\n\n{NOTES_HEADING}\n".lstrip("\n")
    before, after = body[:session.start()].rstrip(), body[session.start():]
    return f"{before}\n\n{NOTES_HEADING}\n\n{after}".lstrip("\n")


def add_to_notes(body: str, text: str, title: str) -> str:
    """Appends a folded callout to the "My notes" section."""
    body = ensure_notes(body)
    start, end = notes_bounds(body)
    quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in text.strip("\n").splitlines())
    callout = f"> [!quote]- {title}\n{quoted}"
    section = body[start:end].rstrip()
    rest = body[end:]
    return f"{body[:start]}{section}\n\n{callout}\n" + (f"\n{rest}" if rest else "")


def replace(body: str, name: str, new: str, moment: str, first: bool = False) -> str:
    """Writes the block `name` with the content `new`.

    The block keeps its place. A note without it gets it at the top (`first`) or before the "My notes"
    section. When the student edited the block, their version moves to "My notes", dated with `moment`.
    """
    block = render(name, new)
    match = _pattern(name).search(body)
    if match is not None:
        old = match.group("content").strip("\n")
        if _hash(old) != match.group("hash") and old.strip() != new.strip("\n").strip():
            body = body[:match.start()] + block + body[match.end():]
            return add_to_notes(body, old, f"Your version of the {name.replace('-', ' ')}, replaced by teach-me on {moment}")
        return body[:match.start()] + block + body[match.end():]
    body = _markers(name).sub("", body)  # a half deleted block : its content stays, as the student's
    if first:
        return f"{block}\n\n{body.lstrip()}".rstrip() + "\n"
    bounds = notes_bounds(body)
    if bounds is None:
        return f"{body.rstrip()}\n\n{block}\n".lstrip("\n")
    before, after = body[:bounds[0]].rstrip(), body[bounds[0]:]
    return f"{before}\n\n{block}\n\n{after}".lstrip("\n")
