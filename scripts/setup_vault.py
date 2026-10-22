"""Makes a teach-me vault usable on its own, for example in a Claude Code cloud session.

Plugins aren't loaded in cloud sessions, but the files of the cloned repository are. This
script writes everything a session needs into the vault repository :

    .claude/skills/teach-me/        a copy of the skill
    .mcp.json                       the MCP server, installed from GitHub with uvx
    .claude/settings.json           a Stop hook ...
    .claude/hooks/sync_vault.sh     ... that commits and pushes the vault in cloud sessions
    CLAUDE.md                       what the vault is, for Claude

Run it again after changing the skill, to update the copy :

    python scripts/setup_vault.py /path/to/the/vault

Only the standard library is used, so any Python 3.10+ works.
"""

import argparse
import json
import shutil
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = PLUGIN_ROOT / "teach-me"
DEFAULT_SOURCE = "git+https://github.com/Gummyy/teach-me-plugin#subdirectory=teach-me-mcp"
HOOK_COMMAND = 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/sync_vault.sh"'

SYNC_SCRIPT = """#!/usr/bin/env bash
# Stop hook : at the end of each turn of a cloud session, commits the changes of the vault
# and pushes them to main, so that they survive the session. Does nothing on your own
# computer, where you sync the vault yourself (obsidian-git, ...).
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git add -A
git diff --cached --quiet && exit 0
git commit -q -m "teach-me: $(date '+%Y-%m-%d %H:%M')" || exit 0
if ! git push -q origin HEAD:main 2>/dev/null; then
  git pull -q --rebase origin main && git push -q origin HEAD:main || echo "teach-me: could not push the vault" >&2
fi
exit 0
"""

CLAUDE_MD = """# teach-me vault

This repository is the memory of the `teach-me` skill : an Obsidian vault holding users, projects, courses, classes, exams and report cards.

- Use the `teach-me` skill to teach, and the `teach-me` MCP tools to read and write the vault. Don't edit the vault files yourself.
- It is data, not code : don't create branches or pull requests. In cloud sessions, a hook commits and pushes the vault to `main` at the end of each turn.
- The skill in `.claude/skills/teach-me/` is a copy, updated with `scripts/setup_vault.py` from the teach-me-plugin repository : don't edit it here.
"""


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8") or "{}")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def copy_skill(vault: Path) -> None:
    target = vault / ".claude" / "skills" / "teach-me"
    shutil.copytree(SKILL_DIR, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("_backup*", "__pycache__"))
    print(f"skill copied to {target}")


def write_mcp_config(vault: Path, source: str) -> None:
    path = vault / ".mcp.json"
    config = read_json(path)
    config.setdefault("mcpServers", {})["teach-me"] = {
        "command": "uvx",
        "args": ["--quiet", "--from", source, "teach-me-mcp"],
        "env": {"TEACH_ME_VAULT": "${CLAUDE_PROJECT_DIR:-.}"},
    }
    write_json(path, config)
    print(f"MCP server declared in {path}")


def write_sync_hook(vault: Path) -> None:
    script = vault / ".claude" / "hooks" / "sync_vault.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(SYNC_SCRIPT, encoding="utf-8", newline="\n")

    path = vault / ".claude" / "settings.json"
    settings = read_json(path)
    stop = settings.setdefault("hooks", {}).setdefault("Stop", [])
    already = any(hook.get("command") == HOOK_COMMAND for group in stop for hook in group.get("hooks", []))
    if not already:
        stop.append({"hooks": [{"type": "command", "command": HOOK_COMMAND}]})
    write_json(path, settings)
    print(f"sync hook declared in {path}")


def write_claude_md(vault: Path, force: bool) -> None:
    path = vault / "CLAUDE.md"
    if path.exists() and not force:
        print(f"{path} already exists, left unchanged (use --force to overwrite)")
        return
    path.write_text(CLAUDE_MD, encoding="utf-8", newline="\n")
    print(f"{path} written")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("vault", type=Path, help="folder of the vault (the root of its git repository)")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help=f"where uvx installs the server from (default: {DEFAULT_SOURCE})")
    parser.add_argument("--force", action="store_true", help="overwrite an existing CLAUDE.md")
    args = parser.parse_args()

    vault = args.vault.expanduser().resolve()
    if not vault.is_dir():
        parser.error(f"{vault} is not a folder")
    copy_skill(vault)
    write_mcp_config(vault, args.source)
    write_sync_hook(vault)
    write_claude_md(vault, args.force)


if __name__ == "__main__":
    main()
