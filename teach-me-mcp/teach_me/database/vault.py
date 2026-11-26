"""Low level access to the vault : paths, time, slugs, links and markdown files.

Nothing in this module knows about users, courses or exams.
"""

from __future__ import annotations

import functools
import json
import os
import re
import time
import unicodedata
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional

import yaml

from teach_me.errors import ToolError
from teach_me.vault import markdown

VAULT_ENV = "TEACH_ME_VAULT"
TIME_FORMAT = "%Y-%m-%dT%H:%M"
"""Format of the `created_at` / `updated_at` properties (understood by Obsidian)."""
SESSION_FORMAT = "%Y-%m-%d %H:%M"
"""Format of the session labels, used as headings in `course.md`."""
MAX_SLUG_LENGTH = 50
LOCK_TIMEOUT = 10.0
"""Seconds a tool call waits for another session to release the vault."""
STALE_LOCK = 60.0
"""A lock older than this many seconds was left by a server that crashed : it is removed."""

_FRONTMATTER = markdown.FRONTMATTER
"""Shared with the `teach-vault` command : the frontmatter is parsed the same way by both skills."""


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
    path = Path(raw).expanduser().resolve()  # a relative path is relative to the working directory
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


class LinkError(Exception):
    """The note targeted by a link doesn't exist."""

    def __init__(self, path: Path):
        super().__init__(f"No note at {path}")
        self.path = path


def link(path: Path) -> str:
    """Obsidian link to an existing note. Obsidian finds notes by file name, so file names must be unique in the vault.

    Raises:
        LinkError: when the note doesn't exist
    """
    if not path.is_file():
        raise LinkError(path)
    return f"[[{path.stem}]]"


def unlink(value: Any) -> str:
    """'[[alice|Alice]]' -> 'alice'. Plain strings are returned unchanged."""
    text = str(value).strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    return re.split(r"[|#]", text, maxsplit=1)[0].strip()


# --------------------------------------------------------------------------- #
# Markdown files
# --------------------------------------------------------------------------- #


def check_links(text: str, field_name: str) -> None:
    """Checks that the wikilinks the model wrote in a markdown field resolve to notes (and headings) of the vault, as Obsidian would.

    Raises:
        ToolError: listing the broken links, so the model can fix the field and call the tool again
    """
    found = [link for link in markdown.links(text or "") if link.note]
    if not found:
        return
    root = vault_path()
    notes = {path.stem: path for path in root.rglob("*.md") if ".teach-me" not in path.relative_to(root).parts}
    attachments = {path.name for path in root.rglob("*") if path.is_file() and path.suffix != ".md"}
    broken = []
    for link in found:
        if link.note in attachments:
            continue
        if link.note not in notes:
            broken.append(f"{link.raw} (no note '{link.note}')")
        elif link.heading and not link.heading.startswith("^") and link.heading.split("#")[-1].strip() not in markdown.headings(notes[link.note].read_text(encoding="utf-8")):
            broken.append(f"{link.raw} (no heading '{link.heading}' in {link.note})")
    if broken:
        raise ToolError(
            f"`{field_name}` links to notes that don't exist in the vault : {', '.join(broken)}. "
            "Link an existing note by its file name (e.g. [[class-convolution]]), or write the name as plain text, then call the tool again."
        )



@dataclass
class Document:
    """A markdown file : its frontmatter (metadata) and its content (body)."""

    path: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    mtime_ns: Optional[int] = field(default=None, repr=False, compare=False)
    """Modification time of the file when it was read : `write` refuses to overwrite a file changed since. None for a new document."""

    @property
    def slug(self) -> str:
        return self.path.stem


class ConflictError(ToolError):
    """A file changed on disk between the moment a tool read it and the moment it writes it."""

    def __init__(self, path: Path):
        super().__init__(f"'{relative(path)}' was changed outside this tool call (Obsidian, a sync or another session) : call the tool again.")
        self.path = path


def _parse_frontmatter(path: Path, text: str) -> tuple[dict, str]:
    try:
        metadata, body = markdown.parse_frontmatter(text)
    except yaml.YAMLError as error:
        raise ToolError(
            f"The frontmatter of '{relative(path)}' is not valid YAML, probably after a manual edit : {error}\n"
            f"Fix it with repair_note(path=\"{relative(path)}\", frontmatter=...), keeping every key and value. "
            f"Its current frontmatter :\n{markdown.split_frontmatter(text)[0]}"
        ) from error
    return metadata, body.strip("\n")


_CONFLICT = re.compile(r"^<{7}(?:[ \t].*)?$.*?^>{7}(?:[ \t].*)?$", re.MULTILINE | re.DOTALL)
"""The markers git leaves in a file it couldn't merge : <<<<<<< ours ... ======= ... >>>>>>> theirs."""


def merge_conflict(path: Path) -> ToolError:
    """The error for a file git couldn't merge (Obsidian Git, or a pull on another device)."""
    return ToolError(
        f"'{relative(path)}' holds git merge conflict markers (<<<<<<< ... ======= ... >>>>>>>) : the vault was synced from two devices that both changed it. "
        "Either resolve the conflict in this file (keep one version between the markers and delete the markers), "
        "or, when nothing of the student's is waiting to be pushed (their answers to an exam above all), reset the vault to the remote version "
        "(`git fetch` then `git reset --hard @{u}`) and call again the tools of this session that were lost. Tell the student in one sentence what you did."
    )


def read(path: Path) -> Document:
    mtime_ns = path.stat().st_mtime_ns  # before reading : a change during the read is caught by `write`
    text = path.read_text(encoding="utf-8")
    if _CONFLICT.search(text):
        raise merge_conflict(path)
    metadata, body = _parse_frontmatter(path, text)
    return Document(path, metadata, body, mtime_ns)


def read_all(paths: Iterable[Path]) -> list[Document]:
    """The notes that can be read among `paths`. A note that can't be (invalid YAML, merge conflict) is skipped, with a warning :
    one broken note must never stop the tools from working on the others."""
    documents = []
    for path in paths:
        try:
            documents.append(read(path))
        except ToolError as error:
            warn(f"Skipped {relative(path)} : {error}")
    return documents


def write_text(path: Path, text: str) -> None:
    """Writes a file atomically : into a temporary file next to it, then renamed over it, so that a crash never leaves a half written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def read_json(path: Path, default: Any = None) -> Any:
    """The content of a JSON file of the tools, or `default` when it doesn't exist.

    Raises:
        ToolError: when the file can't be read, after a merge conflict or a hand edit
    """
    if not path.is_file():
        return default
    text = path.read_text(encoding="utf-8")
    if _CONFLICT.search(text):
        raise merge_conflict(path)
    try:
        return json.loads(text)
    except ValueError as error:
        raise ToolError(
            f"'{relative(path)}' isn't valid JSON anymore ({error}) : it was probably edited by hand. "
            "Restore it from the git history of the vault (`git log -- <file>`, then `git checkout <commit> -- <file>`), then call the tool again."
        ) from None


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write(document: Document) -> None:
    """Writes a document atomically, so that a crash never leaves a half written file. A new note gets an `id` property,
    its file name : the tools find it again under that name if the student renames it.

    Raises:
        ConflictError: when the file changed since the document was read
    """
    if document.mtime_ns is not None and document.path.is_file() and document.path.stat().st_mtime_ns != document.mtime_ns:
        raise ConflictError(document.path)
    if document.mtime_ns is None and not document.path.is_file() and "id" not in document.metadata:
        document.metadata = {"id": document.path.stem, **document.metadata}  # a new note : its stable id, see `renames.py`
    frontmatter = yaml.safe_dump(
        document.metadata, sort_keys=False, allow_unicode=True, width=10_000
    ).strip()
    body = document.body.strip("\n")
    write_text(document.path, f"---\n{frontmatter}\n---\n" + (f"\n{body}\n" if body else ""))
    document.mtime_ns = document.path.stat().st_mtime_ns  # the same document can be written again by the same tool
    written = _written.get()
    if written is not None:
        written.append(document.path)


def repair(path: str, frontmatter: str) -> Document:
    """Replaces the broken frontmatter of a note with `frontmatter`, keeping its content. Refuses a note whose frontmatter is valid."""
    root = vault_path()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or target.suffix != ".md" or not target.is_file():
        raise ToolError(f"There is no note at '{path}' in the vault : give its path relative to the vault, as written in the error.")
    mtime_ns = target.stat().st_mtime_ns
    text = target.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ToolError(f"'{path}' has no frontmatter between two '---' lines : there is nothing to repair.")
    try:
        yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        pass
    else:
        raise ToolError(f"The frontmatter of '{path}' is valid : there is nothing to repair. Use the other tools to change it.")
    try:
        metadata = yaml.safe_load(frontmatter)
    except yaml.YAMLError as error:
        raise ToolError(f"The new `frontmatter` isn't valid YAML either : {error}") from error
    if not isinstance(metadata, dict) or not metadata:
        raise ToolError("The new `frontmatter` must be a YAML mapping of the keys of the note, without the '---' lines.")
    document = Document(target, metadata, match.group(2).strip("\n"), mtime_ns)
    write(document)
    return document


# --------------------------------------------------------------------------- #
# Concurrent sessions
# --------------------------------------------------------------------------- #

_written: ContextVar[Optional[list[Path]]] = ContextVar("written", default=None)
"""The files written by the current tool call, tracked by `serialized`."""
_warnings: ContextVar[Optional[list[str]]] = ContextVar("warnings", default=None)
"""What the current tool call skipped or couldn't resolve, collected by `reporting`."""


def warn(message: str) -> None:
    """Records a problem of the vault that the current tool call worked around : a note it skipped, a link to a missing note."""
    found = _warnings.get()
    if found is not None and message not in found:
        found.append(message)


def reporting(function: Callable) -> Callable:
    """Runs a tool and adds the problems it worked around to its result, as `vault_warnings`, when the result is a dict."""

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        token = _warnings.set([])
        try:
            result = function(*args, **kwargs)
            found = _warnings.get()
        finally:
            _warnings.reset(token)
        if found and isinstance(result, dict):
            result = {**result, "vault_warnings": found}
        return result

    return wrapper


@contextmanager
def locked() -> Iterator[None]:
    """Holds the lock of the vault : a file created exclusively, which works on any file system (fcntl locks don't on /mnt/c)."""
    lock = vault_path() / ".teach-me" / "lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > STALE_LOCK:
                    lock.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() > deadline:
                raise ToolError("The vault is busy : another teach-me session is writing in it. Call the tool again in a few seconds.") from None
            time.sleep(0.05)
    with os.fdopen(descriptor, "w") as file:
        file.write(f"{os.getpid()}\n")
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def serialized(function: Callable) -> Callable:
    """Runs a tool while holding the lock of the vault, so that two sessions never interleave their reads and writes.

    When a file changed outside the call (Obsidian, a sync) before the tool wrote anything, the tool is run
    again on fresh files. Once it has written something, running it again could duplicate it : the error
    tells the model what was written instead.
    """

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        with locked():
            for attempt in (1, 2):
                token = _written.set([])
                try:
                    return function(*args, **kwargs)
                except ConflictError as error:
                    written = _written.get() or []
                    if written:
                        names = ", ".join(relative(path) for path in written)
                        raise ToolError(f"{error} This call had already written : {names}. Check what is missing before calling again.") from error
                    if attempt == 2:
                        raise
                finally:
                    _written.reset(token)

    return wrapper
