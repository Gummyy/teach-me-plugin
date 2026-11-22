"""The bases shipped with the vault : valid YAML, and every view embedded in a note exists."""

import re

import pytest
import yaml

from teach_me.database import dashboards, objects
from teach_me.database import vault as vault_io
from teach_me.tools import start_session


def _check_filter(node, where: str) -> None:
    """A filter is a string, or an object with one key (and, or, not) whose value is a list of filters : Obsidian refuses anything else."""
    if isinstance(node, str):
        return
    assert isinstance(node, dict) and len(node) == 1, f"{where} : {node!r}"
    (key, children), = node.items()
    assert key in ("and", "or", "not") and isinstance(children, list) and children, f"{where} : '{key}' must hold a list of filters, got {children!r}"
    for child in children:
        _check_filter(child, where)


@pytest.mark.parametrize("name", dashboards.BASES)
def test_the_filters_are_well_formed(name):
    base = yaml.safe_load(dashboards.BASES[name])
    if "filters" in base:
        _check_filter(base["filters"], name)
    for view in base["views"]:
        if "filters" in view:
            _check_filter(view["filters"], f"{name}#{view['name']}")


@pytest.mark.parametrize("name", dashboards.BASES)
def test_the_summaries_exist(name):
    base = yaml.safe_load(dashboards.BASES[name])
    defaults = {"Average", "Min", "Max", "Sum", "Range", "Median", "Stddev", "Earliest", "Latest", "Checked", "Unchecked", "Empty", "Filled", "Unique"}
    for view in base["views"]:
        for summary in (view.get("summaries") or {}).values():
            assert summary in defaults or summary in (base.get("summaries") or {}), f"{name}#{view['name']} : {summary}"


@pytest.mark.parametrize("name", dashboards.BASES)
def test_the_bases_are_valid(name):
    base = yaml.safe_load(dashboards.BASES[name])
    formulas = set(base.get("formulas") or {})
    for view in base["views"]:
        assert view["type"] in ("table", "list", "cards", "kanban") and view["name"]
        for column in view.get("order") or []:
            if column.startswith("formula."):
                assert column.removeprefix("formula.") in formulas, f"{name}#{view['name']} : {column}"
        for sort in view.get("sort") or []:
            assert sort["direction"] in ("ASC", "DESC")
    for key in base.get("properties") or {}:
        assert key.split(".")[0] in ("note", "formula", "file"), key  # a bare key is ignored by Obsidian


@pytest.mark.parametrize("dashboard, base", [(dashboards.COURSE_DASHBOARD, "course.base"), (dashboards.HOME_DASHBOARD, "home.base")])
def test_the_embedded_views_exist(dashboard, base):
    views = {view["name"] for view in yaml.safe_load(dashboards.BASES[base])["views"]}
    embedded = re.findall(r"!\[\[([^#\]]+)#([^\]]+)\]\]", dashboard)
    assert embedded and all(file == base and view in views for file, view in embedded)


def test_the_vault_gets_its_views(course, vault):
    assert (vault / "bases" / "course.base").read_text(encoding="utf-8") == dashboards.COURSE_BASE
    home = vault_io.read(vault / "Home.md")
    assert home.metadata["type"] == "home" and "![[home.base#Exams to answer]]" in home.body
    home.body = home.body.replace("![[home.base#Courses]]", "")
    vault_io.write(home)
    start_session("app", user="alice")
    assert "![[home.base#Courses]]" in vault_io.read(vault / "Home.md").body
    body = objects.get_course(course).body
    for view in ("Last steps", "Next steps", "Plan", "Skills", "Exams", "Projects", "Resources"):
        assert f"![[course.base#{view}]]" in body
