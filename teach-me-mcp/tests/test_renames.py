"""A note renamed or moved in Obsidian is put back by start_session, under the name its `id` gives : its links point to it again,
the name the student gave is kept as an alias, and the hidden data found by the name (the grades of an exam) still applies."""

import shutil

from teach_me.database import migrations, objects, renames
from teach_me.database import vault as vault_io
from teach_me.tools import list_courses, migrate_vault, start_session
from tests.test_source_of_truth import _corrected, _grades

start = vault_io.reporting(start_session)


def _obsidian_rename(vault, path, name):
    """What Obsidian does when the student renames a note : the file, then every link to it in the vault."""
    target = path.with_name(f"{name}.md")
    path.rename(target)
    for note in vault.rglob("*.md"):
        text = note.read_text(encoding="utf-8")
        if f"[[{path.stem}" in text:
            note.write_text(text.replace(f"[[{path.stem}]]", f"[[{name}]]").replace(f"[[{path.stem}|", f"[[{name}|"), encoding="utf-8")
    return target


def _warnings(result):
    return " ".join(result.get("vault_warnings") or [])


def test_every_note_has_an_id(course, vault):
    start_session("terminal", "alice", course)
    for path in [vault / "Home.md", *vault.glob("users/*.md"), *vault.glob("skills/*.md"), *vault.glob("projects/*.md"), *vault.glob("courses/**/*.md")]:
        assert vault_io.read(path).metadata["id"] == path.stem


def test_a_renamed_skill_is_put_back(course, vault):
    exam, _ = _corrected(course, vault)
    before = _grades()
    renamed = _obsidian_rename(vault, objects.skill_file("convolution"), "Convolutions")
    assert "[[Convolutions]]" in objects.get_course(course).metadata["skills"]
    result = start("terminal", "alice", course)
    assert not renamed.exists() and objects.skill_file("convolution").is_file()
    assert "skills/Convolutions.md → skills/skill-convolution.md" in _warnings(result)
    assert "[[skill-convolution]]" in objects.get_course(course).metadata["skills"]
    assert not any("[[Convolutions" in note.read_text(encoding="utf-8") for note in vault.rglob("*.md"))
    assert vault_io.read(objects.skill_file("convolution")).metadata["aliases"] == ["Convolutions"]
    assert _grades() == before and "convolution" in [skill["slug"] for skill in result["course"]["skills"]]


def test_a_renamed_exam_keeps_its_grades(course, vault):
    exam, path = _corrected(course, vault)
    before = _grades()
    _obsidian_rename(vault, path, "My first quiz")
    assert _grades() != before  # its hidden data is found by its name
    start("terminal", "alice", course)
    assert path.is_file() and _grades() == before


def test_a_moved_class_and_a_renamed_course_folder_are_put_back(course, vault):
    lesson = vault / "courses" / course / "classes" / "class-convolution.md"
    lesson.rename(vault / "class-convolution.md")
    (vault / "courses" / course).rename(vault / "courses" / "vision")
    assert [c["slug"] for c in list_courses("alice")] == []
    result = start("terminal", "alice")
    assert [c["slug"] for c in result["courses"]] == [course]
    assert lesson.is_file() and not (vault / "courses" / "vision").exists()
    assert "convolution" in [step["slug"] for step in start("terminal", "alice", course)["course"]["plan"]["next_steps"]]


def test_a_renamed_course_note_and_user_note_are_put_back(course, vault):
    _obsidian_rename(vault, objects.course_file(course), "My vision course")
    _obsidian_rename(vault, objects.user_file("alice"), "Me")
    result = start("terminal")
    assert result["user"]["slug"] == "alice" and [c["slug"] for c in result["courses"]] == [course]
    lesson = vault_io.read(vault / "courses" / course / "classes" / "class-convolution.md")
    assert lesson.metadata["course"] == f"[[course-{course}]]"


def test_a_copy_is_left_alone_with_a_warning(course, vault):
    skill = objects.skill_file("convolution")
    shutil.copy(skill, skill.with_name("skill-convolution 1.md"))
    result = start("terminal", "alice", course)
    assert skill.with_name("skill-convolution 1.md").is_file() and skill.is_file()
    assert "skill-convolution 1.md has the id of skills/skill-convolution.md" in _warnings(result)


def test_a_lost_id_is_given_back(course, vault):
    skill = objects.skill_file("convolution")
    skill.write_text(skill.read_text(encoding="utf-8").replace("id: skill-convolution\n", ""), encoding="utf-8")
    assert "id" not in vault_io.read(skill).metadata
    start("terminal", "alice", course)
    assert vault_io.read(skill).metadata["id"] == "skill-convolution"
    assert "vault_warnings" not in start("terminal", "alice", course)


def test_links_with_an_alias_or_a_folder_are_fixed(vault):
    (vault / "a.md").write_text("---\nx: '[[Old|shown]]'\n---\n[[Old]] ![[notes/Old#Part]] [[Old\\|in a table]] [[Older]]\n", encoding="utf-8")
    assert renames.relink("Old", "skill-new") == ["a.md"]
    assert (vault / "a.md").read_text(encoding="utf-8") == "---\nx: '[[skill-new|shown]]'\n---\n[[skill-new]] ![[skill-new#Part]] [[skill-new\\|in a table]] [[Older]]\n"


def test_migration_4_gives_every_note_an_id(course, vault):
    start_session("terminal", "alice", course)
    notes = [*vault.glob("skills/*.md"), *vault.glob("courses/**/*.md")]
    for path in notes:
        document = vault_io.read(path)
        document.metadata.pop("id")
        vault_io.write(document)
    (vault / ".teach-me").mkdir(exist_ok=True)
    (vault / ".teach-me" / "version").write_text("3\n")
    result = migrate_vault()
    assert result["to"] == migrations.current_version()
    assert all(vault_io.read(path).metadata["id"] == path.stem for path in notes)
    assert len([change for change in result["changes"] if change.endswith(": id")]) == len(notes)


def test_a_change_of_case_is_put_back_without_an_alias(course, vault):
    skill = objects.skill_file("convolution")
    skill.rename(skill.with_name("Skill-convolution.md"))
    result = start("terminal", "alice", course)
    assert [path.name for path in vault.glob("skills/*onvolution.md")] == ["skill-convolution.md"]
    assert "aliases" not in vault_io.read(skill).metadata and "alias" not in _warnings(result)
