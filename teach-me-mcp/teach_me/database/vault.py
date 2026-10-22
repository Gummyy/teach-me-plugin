"""Low level access to the vault : paths, time, slugs, links and markdown files.

Nothing in this module knows about users, courses or exams.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from teach_me.errors import ToolError

VAULT_ENV = "TEACH_ME_VAULT"
TIME_FORMAT = "%Y-%m-%dT%H:%M"
"""Format of the `created_at` / `updated_at` properties (understood by Obsidian)."""
SESSION_FORMAT = "%Y-%m-%d %H:%M"
"""Format of the session labels, used as headings in `course.md`."""
MAX_SLUG_LENGTH = 50

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.DOTALL)


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #


def vault_path() -> Path:
    """Returns the root of the vault, read from the TEACH_ME_VAULT environment variable."""
    raw = os.environ.get(VAULT_ENV)
    if not raw:
        raise ToolError(
            f"The {VAULT_ENV} environment variable is not set. "
            "Ask the user to set it to the folder of their vault in the configuration of the MCP server."
        )
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative(path: Path) -> str:
    """Path of a file relative to the vault, with forward slashes."""
    return path.relative_to(vault_path()).as_posix()


# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #


def now() -> datetime:
    """Current local time, to the minute."""
    return datetime.now().replace(second=0, microsecond=0)


def format_time(moment: datetime) -> str:
    return moment.strftime(TIME_FORMAT)


def format_session(moment: datetime) -> str:
    return moment.strftime(SESSION_FORMAT)


def parse_time(value: Any) -> Optional[datetime]:
    """Parses a time written by a tool or by hand. Returns None if it can't be parsed."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if not isinstance(value, str):
        return None
    for fmt in (TIME_FORMAT, SESSION_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Slugs and links
# --------------------------------------------------------------------------- #


def slugify(text: str) -> str:
    """'Réseaux de neurones convolutifs !' -> 'reseaux-de-neurones-convolutifs'"""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(slug) > MAX_SLUG_LENGTH:
        slug = slug[:MAX_SLUG_LENGTH].rsplit("-", 1)[0]
    return slug or "untitled"


def unique_slug(base: str, exists) -> str:
    """Adds -2, -3, ... to `base` until `exists(slug)` is False."""
    slug, counter = base, 2
    while exists(slug):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def link(slug: str) -> str:
    """Obsidian link to a note."""
    return f"[[{slug}]]"


def unlink(value: Any) -> str:
    """'[[alice|Alice]]' -> 'alice'. Plain strings are returned unchanged."""
    text = str(value).strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    return re.split(r"[|#]", text, maxsplit=1)[0].strip()


# --------------------------------------------------------------------------- #
# Markdown files
# --------------------------------------------------------------------------- #


@dataclass
class Document:
    """A markdown file : its frontmatter (metadata) and its content (body)."""

    path: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def slug(self) -> str:
        return self.path.stem


def read(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        return Document(path, {}, text.strip("\n"))
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        raise ToolError(f"The frontmatter of '{path.name}' is not valid YAML : {error}") from error
    if not isinstance(metadata, dict):
        metadata = {}
    return Document(path, metadata, match.group(2).strip("\n"))


def write(document: Document) -> None:
    """Writes a document atomically, so that a crash never leaves a half written file."""
    document.path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump(
        document.metadata, sort_keys=False, allow_unicode=True, width=10_000
    ).strip()
    body = document.body.strip("\n")
    text = f"---\n{frontmatter}\n---\n" + (f"\n{body}\n" if body else "")
    temporary = document.path.with_name(document.path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(document.path)
