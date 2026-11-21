"""The `teach-vault` command.

    teach-vault plan <vault> [--check]       rebuild the generated tables of the course notes
    teach-vault check <vault>                what fails in the vault, exit 1 if anything does
    teach-vault export <vault> <destination> [--force]
                                             the student vault, then the link checks on it
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def run_plan(vault_path: Path, check_only: bool) -> int:
    from teach_me.vault import plan
    from teach_me.vault.notes import Vault

    vault = Vault(vault_path)
    if not vault.courses():
        print(f"{vault.root}: no note with `type: course`", file=sys.stderr)
        return 1
    results = plan.rebuild(vault)
    for result in results:
        name = result.course.relative
        for block in result.missing:
            print(f"{name}: no '%% {block}:start %%' … '%% {block}:end %%' block, left out")
        if check_only:
            print(f"{name}: {'out of date, run teach-vault plan' if result.changed else 'up to date'}")
        else:
            print(f"{name}: {'rebuilt' if result.changed else 'already up to date'}")
    if check_only:
        return 1 if any(r.changed for r in results) else 0
    plan.write(results)
    return 0


def run_check(vault_path: Path) -> int:
    from teach_me.vault.check import check, postponed
    from teach_me.vault.notes import Vault

    vault = Vault(vault_path)
    errors = check(vault)
    for error in errors:
        print(error)
    for exam in postponed(vault):
        print(f"{exam}: expected outcome or correction postponed (> [!todo])")
    print(f"{len(vault.notes)} notes checked, {len(errors)} failure(s).")
    return 1 if errors else 0


def run_export(vault_path: Path, destination: Path, force: bool) -> int:
    from teach_me.vault.check import check_links
    from teach_me.vault.export import ExportError, export
    from teach_me.vault.notes import Vault

    try:
        result = export(vault_path, destination, force)
    except ExportError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{result.copied} files copied to {destination}, {result.left_out} teacher notes left out, {result.unlinked} links to them turned into text.")
    student = Vault(destination)
    errors = check_links(student)
    for error in errors:
        print(error)
    print(f"Student vault : {len(student.notes)} notes checked, {len(errors)} failure(s).")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="teach-vault", description="The vault scripts of the teach-them skill.")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="rebuild the plan, extra activities and skills coverage tables of every course note")
    plan_parser.add_argument("vault", type=Path)
    plan_parser.add_argument("--check", action="store_true", help="only report whether the tables are up to date (exit 1 if not)")
    check_parser = commands.add_parser("check", help="links, skills evaluated, recalls, exam sections, teacher links")
    check_parser.add_argument("vault", type=Path)
    export_parser = commands.add_parser("export", help="build the student vault")
    export_parser.add_argument("vault", type=Path)
    export_parser.add_argument("destination", type=Path)
    export_parser.add_argument("--force", action="store_true", help="replace the destination if it exists")
    args = parser.parse_args(argv)

    if args.command == "plan":
        return run_plan(args.vault, args.check)
    if args.command == "check":
        return run_check(args.vault)
    return run_export(args.vault, args.destination, args.force)


if __name__ == "__main__":
    sys.exit(main())
