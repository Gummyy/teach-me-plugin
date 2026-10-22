from pathlib import Path

import pytest

from teach_me.database import vault
from teach_me.database.vault import Document
from teach_me.errors import ToolError


def test_missing_vault_env(monkeypatch):
    monkeypatch.delenv(vault.VAULT_ENV, raising=False)
    with pytest.raises(ToolError, match=vault.VAULT_ENV):
        vault.vault_path()


def test_slugify():
    assert vault.slugify("Réseaux de neurones convolutifs !") == "reseaux-de-neurones-convolutifs"
    assert vault.slugify("???") == "untitled"
    assert len(vault.slugify("word " * 50)) <= vault.MAX_SLUG_LENGTH


def test_unique_slug():
    taken = {"alice", "alice-2"}
    assert vault.unique_slug("alice", taken.__contains__) == "alice-3"
    assert vault.unique_slug("bob", taken.__contains__) == "bob"


def test_links():
    assert vault.link("alice") == "[[alice]]"
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
