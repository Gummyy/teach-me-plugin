import os
import time
from pathlib import Path

import pytest

from teach_me.database import vault
from teach_me.database import vault as vault_module  # the `vault` fixture shadows the module in the tests below
from teach_me.database.vault import Document
from teach_me.errors import ToolError
from teach_me.tools import repair_note


def vault_module_write(path: Path, metadata: dict) -> None:
    vault_module.write(Document(path, metadata))


def test_missing_vault_env(monkeypatch):
    monkeypatch.delenv(vault.VAULT_ENV, raising=False)
    with pytest.raises(ToolError, match=vault.VAULT_ENV):
        vault.vault_path()


def test_relative_vault_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(vault.VAULT_ENV, ".")
    assert vault.vault_path() == tmp_path.resolve()


def test_slugify():
    assert vault.slugify("Réseaux de neurones convolutifs !") == "reseaux-de-neurones-convolutifs"
    assert vault.slugify("???") == "untitled"
    assert len(vault.slugify("word " * 50)) <= vault.MAX_SLUG_LENGTH


def test_unique_slug():
    taken = {"alice", "alice-2"}
    assert vault.unique_slug("alice", taken.__contains__) == "alice-3"
    assert vault.unique_slug("bob", taken.__contains__) == "bob"


def test_links(tmp_path: Path):
    note = tmp_path / "user-alice.md"
    with pytest.raises(vault.LinkError):
        vault.link(note)
    note.write_text("", encoding="utf-8")
    assert vault.link(note) == "[[user-alice]]"
    assert vault.unlink("[[alice|Alice]]") == "alice"
    assert vault.unlink("[[course#2026-10-20 10:30]]") == "course"
    assert vault.unlink("alice") == "alice"


def test_parse_time():
    assert vault.parse_time("2026-10-20T10:30").hour == 10
    assert vault.parse_time("2026-10-20 10:30").minute == 30
    assert vault.parse_time("yesterday") is None
    assert vault.parse_time(None) is None


def test_write_and_read_round_trip(tmp_path: Path):
    path = tmp_path / "notes" / "note.md"
    vault.write(Document(path, {"title": "Été", "user": "[[alice]]", "tags": ["a", "b"]}, "# Body\n\nText"))
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\ntitle: Été\n")  # keys keep their order, unicode isn't escaped
    document = vault.read(path)
    assert document.metadata == {"title": "Été", "user": "[[alice]]", "tags": ["a", "b"]}
    assert document.body == "# Body\n\nText"
    assert document.slug == "note"


def test_read_file_without_frontmatter(tmp_path: Path):
    path = tmp_path / "plain.md"
    path.write_text("Just text\n", encoding="utf-8")
    assert vault.read(path).metadata == {}
    assert vault.read(path).body == "Just text"


def test_write_refuses_a_file_changed_since_it_was_read(vault):
    path = vault / "note.md"
    vault_module_write(path, {"a": 1})
    document = vault_module.read(path)
    os.utime(path, ns=(document.mtime_ns + 10_000_000, document.mtime_ns + 10_000_000))  # edited in Obsidian
    document.metadata["a"] = 2
    with pytest.raises(vault_module.ConflictError, match="changed outside this tool call"):
        vault_module.write(document)
    fresh = vault_module.read(path)
    fresh.metadata["a"] = 2
    vault_module.write(fresh)
    vault_module.write(fresh)  # the same document can be written twice
    assert vault_module.read(path).metadata == {"a": 2}


def test_serialized_runs_again_when_nothing_was_written(vault):
    path = vault / "note.md"
    vault_module_write(path, {"count": 0})
    calls = []

    def tool():
        document = vault_module.read(path)
        if not calls:  # someone else edits the note between the read and the write of the first call
            os.utime(path, ns=(document.mtime_ns + 10_000_000, document.mtime_ns + 10_000_000))
        calls.append(1)
        document.metadata["count"] += 1
        vault_module.write(document)
        return document.metadata["count"]

    assert vault_module.serialized(tool)() == 1 and len(calls) == 2
    assert not (vault / ".teach-me" / "lock").exists()  # released


def test_serialized_doesnt_run_again_after_a_write(vault):
    first, second = vault / "first.md", vault / "second.md"
    vault_module_write(second, {})

    def tool():
        document = vault_module.read(second)
        vault_module_write(first, {})
        os.utime(second, ns=(document.mtime_ns + 10_000_000, document.mtime_ns + 10_000_000))
        vault_module.write(document)

    with pytest.raises(ToolError, match="already written : first.md"):
        vault_module.serialized(tool)()


def test_lock_waits_then_gives_up(vault, monkeypatch):
    monkeypatch.setattr(vault_module, "LOCK_TIMEOUT", 0.2)
    with vault_module.locked():
        with pytest.raises(ToolError, match="vault is busy"):
            with vault_module.locked():
                pass
    with vault_module.locked():  # released
        pass


def test_stale_lock_is_removed(vault):
    lock = vault / ".teach-me" / "lock"
    lock.parent.mkdir()
    lock.write_text("1234\n")
    old = time.time() - vault_module.STALE_LOCK - 1
    os.utime(lock, (old, old))
    with vault_module.locked():
        assert lock.read_text() != "1234\n"


def test_broken_frontmatter_is_repaired(vault):
    path = vault / "users" / "user-alice.md"
    path.parent.mkdir()
    path.write_text("---\nname: Alice\npreferences: {language: french\n---\n\nLikes photography\n", encoding="utf-8")
    with pytest.raises(ToolError, match=r"(?s)not valid YAML.*repair_note\(path=\"users/user-alice.md\".*preferences: \{language: french"):
        vault_module.read(path)
    with pytest.raises(ToolError, match="isn't valid YAML either"):
        repair_note("users/user-alice.md", "name: [Alice")
    assert repair_note("users/user-alice.md", "name: Alice\npreferences: {language: french}") == {"path": "users/user-alice.md", "keys": ["name", "preferences"]}
    document = vault_module.read(path)
    assert document.metadata == {"name": "Alice", "preferences": {"language": "french"}} and document.body == "Likes photography"
    with pytest.raises(ToolError, match="nothing to repair"):
        repair_note("users/user-alice.md", "name: Bob")
    with pytest.raises(ToolError, match="no note at '../outside.md'"):
        repair_note("../outside.md", "a: 1")
