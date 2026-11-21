"""The plugin's hooks : `teach-vault hook record` (PostToolUse) and `teach-vault hook stop` (Stop).

Plugin hooks fire in every session where the plugin is enabled, in any project : `record` only notes
which `teach-them` vault an edit touched, and exits at once for any other file. `stop` rebuilds the
plan and checks each recorded vault once, at the end of the turn : in the middle of a turn, links
point to notes not written yet, and rewriting the course note would make the model's next edit of
it fail.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional, TextIO

DATA_ENV = "CLAUDE_PLUGIN_DATA"
MAX_LINES = 40
"""Failures printed at most, so that a broken vault doesn't flood the model."""


def _pending_file(session_id: str) -> Optional[Path]:
    data = os.environ.get(DATA_ENV)
    if not data:
        return None
    name = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "session")
    return Path(data) / "teach-them" / f"pending-{name}.txt"


def _read_input(stdin: TextIO) -> dict:
    try:
        data = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _pending(file: Path) -> list[str]:
    try:
        return [line for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return []


def record(stdin: TextIO = sys.stdin) -> int:
    """PostToolUse on Write|Edit|MultiEdit : remembers the vault of the edited note, if it is a `teach-them` vault."""
    event = _read_input(stdin)
    tool_input = event.get("tool_input") or {}
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(path, str) or not path.endswith(".md"):
        return 0
    file = _pending_file(str(event.get("session_id", "")))
    if file is None:
        return 0
    from teach_me.vault.notes import find_vault

    target = Path(path)
    if not target.is_absolute():
        target = Path(str(event.get("cwd") or ".")) / target
    vault = find_vault(target)
    if vault is None:
        return 0
    pending = _pending(file)
    if str(vault) not in pending:
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("a", encoding="utf-8") as out:
            out.write(f"{vault}\n")
    return 0


def _failures(vault_path: Path) -> list[str]:
    from teach_me.vault import plan
    from teach_me.vault.check import check
    from teach_me.vault.notes import Vault

    plan.write(plan.rebuild(Vault(vault_path)))
    return check(Vault(vault_path))


def stop(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Stop : rebuilds the plan of each recorded vault, then checks it.

    The first time something fails, exits 2 with the failures on stderr : the model fixes them before
    handing back, and the vault stays recorded. When the model already had its chance
    (`stop_hook_active`), the remaining failures are shown to the user without blocking again.
    """
    event = _read_input(stdin)
    file = _pending_file(str(event.get("session_id", "")))
    if file is None:
        return 0
    vaults = [Path(line) for line in _pending(file)]
    if not vaults:
        return 0
    report = []
    for vault in vaults:
        if not vault.is_dir():
            continue
        failures = _failures(vault)
        if failures:
            shown = failures[:MAX_LINES] + ([f"... and {len(failures) - MAX_LINES} more"] if len(failures) > MAX_LINES else [])
            report.append(f"teach-vault check {vault} : {len(failures)} failure(s)\n" + "\n".join(f"- {line}" for line in shown))
    if report and not event.get("stop_hook_active"):
        print("\n\n".join(report) + "\n\nFix these in the notes (the generated tables come from their properties), then hand back.", file=stderr)
        return 2
    file.unlink(missing_ok=True)
    if report:
        message = "teach-them : the vault still has failures, run teach-vault check to see them.\n\n" + "\n\n".join(report)
        json.dump({"systemMessage": message}, stdout)
    return 0
