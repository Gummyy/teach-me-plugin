"""The plugin's hooks : `teach-vault hook record` and `teach-vault hook stop`."""

import io
import json
import shutil

import pytest

from teach_me.vault import hooks
from tests.test_teach_vault import COURSE, FIXTURE, edit


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv(hooks.DATA_ENV, str(tmp_path / "data"))
    copy = tmp_path / "vault"
    shutil.copytree(FIXTURE, copy)
    return copy


def event(**fields) -> io.StringIO:
    return io.StringIO(json.dumps({"session_id": "s1", "cwd": "/", **fields}))


def record(path) -> int:
    return hooks.record(event(tool_name="Edit", tool_input={"file_path": str(path)}))


def stop(active=False) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = hooks.stop(event(stop_hook_active=active), out, err)
    return code, out.getvalue(), err.getvalue()


def pending(tmp_path) -> list[str]:
    file = tmp_path / "data" / "teach-them" / "pending-s1.txt"
    return file.read_text().split() if file.exists() else []


def test_record_ignores_files_outside_a_teach_them_vault(vault, tmp_path):
    (tmp_path / "notes.md").write_text("# Notes\n")
    assert record(tmp_path / "notes.md") == 0
    assert record(vault / "courses/sql/helpers/cheat-sheet/queries.sql") == 0
    assert pending(tmp_path) == []
    assert stop() == (0, "", "")


def test_record_remembers_the_vault_once(vault, tmp_path):
    record(vault / "courses/sql/classes/class-joins.md")
    record(vault / "skills/skill-select.md")
    assert pending(tmp_path) == [str(vault.resolve())]


def test_record_without_plugin_data_does_nothing(vault, tmp_path, monkeypatch):
    monkeypatch.delenv(hooks.DATA_ENV)
    assert record(vault / "skills/skill-select.md") == 0
    assert hooks.stop(event(), io.StringIO(), io.StringIO()) == 0


def test_stop_rebuilds_the_plan_and_clears_the_list(vault, tmp_path):
    edit(vault, "courses/sql/classes/class-joins.md", "duration: 35", "duration: 50")
    record(vault / "courses/sql/classes/class-joins.md")
    assert stop() == (0, "", "")
    assert "| 📖 class | 50 |" in (vault / COURSE).read_text(encoding="utf-8")
    assert pending(tmp_path) == []


def test_stop_blocks_once_on_a_failure_then_reports_it(vault, tmp_path):
    edit(vault, "courses/sql/classes/class-joins.md", "[[class-select#Content|the first class]]", "[[class-selekt]]")
    record(vault / "courses/sql/classes/class-joins.md")

    code, out, err = stop()
    assert code == 2 and "[[class-selekt]] → no such note" in err and out == ""
    assert pending(tmp_path) == [str(vault.resolve())]  # checked again at the next stop

    code, out, err = stop(active=True)
    assert code == 0 and err == ""
    assert "[[class-selekt]]" in json.loads(out)["systemMessage"]
    assert pending(tmp_path) == []


def test_stop_passes_once_the_model_fixed_the_failure(vault, tmp_path):
    edit(vault, "courses/sql/classes/class-joins.md", "[[class-select#Content|the first class]]", "[[class-selekt]]")
    record(vault / "courses/sql/classes/class-joins.md")
    assert stop()[0] == 2
    edit(vault, "courses/sql/classes/class-joins.md", "[[class-selekt]]", "[[class-select]]")
    assert stop(active=True) == (0, "", "")
