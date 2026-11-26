"""Migrations of the vault : what each version of teach-me changes in the notes of an existing vault.

The version of a vault is written in `.teach-me/version`. A vault without this file is at version 0
when it already holds notes written by teach-me, and at the current version when it is new. The tools
refuse to work on an older vault until `migrate_vault` (or the `teach-me-migrate` command) brought it
up to date : reading notes of an older format would give wrong answers.

`MIGRATIONS[n]` brings a vault from version n to version n + 1. A migration only uses the functions of
the database modules, and returns one line per note it changed. Before running them, the notes are
copied into `.teach-me/backups/<date>/` with the bases and Home.md, so that nothing is ever lost.
"""

from __future__ import annotations

import argparse
import functools
import os
import shutil
from pathlib import Path
from typing import Callable

from teach_me.database import migration_1, migration_2, migration_3, migration_4, vault
from teach_me.errors import ToolError

MIGRATIONS: list[Callable[[], list[str]]] = [migration_1.run, migration_2.run, migration_3.run, migration_4.run]
"""MIGRATIONS[n] brings a vault from version n to version n + 1, and returns what it changed."""
DATA_FOLDERS = ("users", "projects", "skills", "courses")
"""The folders of the notes written by the tools : a vault holding one of them was written by teach-me."""


def current_version() -> int:
    return len(MIGRATIONS)


def version_file() -> Path:
    return vault.vault_path() / ".teach-me" / "version"


def _write_version(version: int) -> None:
    vault.write_text(version_file(), f"{version}\n")


def vault_version() -> int:
    """The version of the vault. A new vault gets the current version."""
    file = version_file()
    if file.is_file():
        try:
            return int(file.read_text(encoding="utf-8").strip())
        except ValueError:
            raise ToolError(f"{vault.relative(file)} should only hold the version of the vault, a number : fix it or delete it.") from None
    root = vault.vault_path()
    if any(any((root / folder).glob("*/*.md") if folder == "courses" else (root / folder).glob("*.md")) for folder in DATA_FOLDERS):
        return 0
    _write_version(current_version())
    return current_version()


def check_current() -> None:
    """Raises a ToolError when the vault must be migrated first, or was written by a newer teach-me."""
    version, current = vault_version(), current_version()
    if version < current:
        raise ToolError(
            f"This vault was written by an older version of teach-me (vault version {version}, the tools need {current}). "
            "Call migrate_vault, tell the student in one sentence that their notes were updated to the new format, then call this tool again."
        )
    if version > current:
        raise ToolError(
            f"This vault was written by a newer version of teach-me (vault version {version}, these tools know {current}). "
            "Ask the student to update the teach-me plugin."
        )


def requires_current(function: Callable) -> Callable:
    """Runs a tool only on a vault at the current version."""

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        check_current()
        return function(*args, **kwargs)

    return wrapper


def _backup() -> Path:
    """Copies the notes, the views and the hidden data of the vault into .teach-me/backups/<date>/."""
    root = vault.vault_path()
    target = root / ".teach-me" / "backups" / vault.now().strftime("%Y-%m-%d-%H%M")
    target = Path(vault.unique_slug(str(target), lambda candidate: Path(candidate).exists()))
    for folder in DATA_FOLDERS:
        if (root / folder).is_dir():
            shutil.copytree(root / folder, target / folder, ignore=shutil.ignore_patterns("*.tmp"))
    if (root / "bases").is_dir():
        shutil.copytree(root / "bases", target / "bases")
    if (root / "Home.md").is_file():
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / "Home.md", target / "Home.md")
    for folder in ("solutions", "grades", "exams"):
        if (root / ".teach-me" / folder).is_dir():
            shutil.copytree(root / ".teach-me" / folder, target / ".teach-me" / folder)
    return target


def migrate() -> dict:
    """Brings the vault to the current version. Returns {"from", "to", "backup", "changes"}."""
    version, current = vault_version(), current_version()
    if version > current:
        check_current()
    if version == current:
        return {"from": version, "to": current, "backup": None, "changes": []}
    backup = _backup()
    changes: list[str] = []
    for number in range(version, current):
        changes += MIGRATIONS[number]()
        _write_version(number + 1)
    return {"from": version, "to": current, "backup": vault.relative(backup), "changes": changes}


def main(argv: list[str] | None = None) -> int:
    """Entry point of the `teach-me-migrate` command."""
    parser = argparse.ArgumentParser(description="Brings a teach-me vault to the format of this version of the tools. The notes are backed up first, in .teach-me/backups/.")
    parser.add_argument("vault", type=Path, help="folder of the vault")
    args = parser.parse_args(argv)
    if not args.vault.is_dir():
        parser.error(f"{args.vault} is not a folder")
    os.environ[vault.VAULT_ENV] = str(args.vault)
    with vault.locked():
        try:
            result = migrate()
        except ToolError as error:
            print(error)
            return 1
    if result["from"] == result["to"]:
        print(f"Already at version {result['to']} : nothing to do.")
        return 0
    for change in result["changes"]:
        print(change)
    print(f"Migrated from version {result['from']} to {result['to']}. Backup : {result['backup']}")
    return 0
