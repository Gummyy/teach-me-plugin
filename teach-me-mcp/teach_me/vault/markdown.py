"""Parsing of the Obsidian notes : frontmatter, wikilinks, headings and teacher blocks.

Shared by the `teach-me` tools (teach_me.database.vault) and the `teach-vault` command.
Nothing here touches the disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import yaml

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.DOTALL)
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"!?\[\[([^\]\n]+?)\]\]")
HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
TEACHER_BLOCK = re.compile(r"^%% teacher:start %%[ \t]*$.*?^%% teacher:end %%[ \t]*$\n?", re.MULTILINE | re.DOTALL)
TEACHER_START = "%% teacher:start %%"
TEACHER_END = "%% teacher:end %%"


def split_frontmatter(text: str) -> tuple[Optional[str], str]:
    """'---\\nkey: value\\n---\\nbody' -> ('key: value', 'body'). (None, text) when there is no frontmatter."""
    match = FRONTMATTER.match(text)
    if not match:
        return None, text
    return match.group(1), match.group(2)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """The properties and the body of a note.

    Raises:
        yaml.YAMLError: when the frontmatter isn't valid YAML
    """
    raw, body = split_frontmatter(text)
    if raw is None:
        return {}, text
    metadata = yaml.safe_load(raw) or {}
    return (metadata if isinstance(metadata, dict) else {}), body


def strip_code(text: str) -> str:
    """Removes the fenced blocks and the inline code, where a `[[...]]` is not a link."""
    return INLINE_CODE.sub("", FENCE.sub("", text))


@dataclass(frozen=True)
class Link:
    note: str
    """The target note, without the folder ('' for a link to a heading of the same note)."""
    heading: Optional[str]
    """The heading anchor, or None. Block references (`#^id`) are kept with their '^'."""
    alias: Optional[str]
    raw: str
    """The whole `[[...]]` or `![[...]]`, as written."""
    start: int
    """Offset of the link in the text it was found in."""


def parse_link(inside: str) -> tuple[str, Optional[str], Optional[str]]:
    """'folder/note#Heading\\|Alias' -> ('note', 'Heading', 'Alias'). The path of an attachment ('img/a.png') keeps its name ('a.png')."""
    target, _, alias = inside.replace("\\|", "|").partition("|")
    note, _, heading = target.partition("#")
    note = note.strip().rsplit("/", 1)[-1]
    if note.endswith(".md"):
        note = note[:-3]
    return note, (heading.strip() or None), (alias.strip() or None)


def links(text: str) -> list[Link]:
    """The wikilinks and embeds of a text, outside code."""
    found = []
    for match in LINK.finditer(_blank_code(text)):
        note, heading, alias = parse_link(match.group(1))
        found.append(Link(note, heading, alias, match.group(0), match.start()))
    return found


def _blank_code(text: str) -> str:
    """The text with its code replaced by spaces, so that the offsets of the links stay those of the original."""
    blank = lambda match: re.sub(r"[^\n]", " ", match.group(0))  # noqa: E731
    return INLINE_CODE.sub(blank, FENCE.sub(blank, text))


def headings(text: str) -> set[str]:
    return set(HEADING.findall(strip_code(text)))


def teacher_spans(text: str) -> list[tuple[int, int]]:
    """The (start, end) offsets of the teacher blocks of a note."""
    return [(m.start(), m.end()) for m in TEACHER_BLOCK.finditer(text)]


def remove_teacher_blocks(text: str) -> str:
    return TEACHER_BLOCK.sub("", text)


def title(body: str, default: str) -> str:
    """The first level 1 heading of a note, else `default`."""
    match = re.search(r"^# (.+?)\s*$", FENCE.sub("", body), re.MULTILINE)
    return match.group(1).strip() if match else default


def unlink(value: Any) -> str:
    """'[[skill-sql|SQL]]' -> 'skill-sql'. Plain strings are returned unchanged."""
    text = str(value).strip()
    if text.startswith("[[") and text.endswith("]]"):
        return parse_link(text[2:-2])[0]
    return text
