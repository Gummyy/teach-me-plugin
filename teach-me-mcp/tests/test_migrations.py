import asyncio

import pytest
from fastmcp import Client

from teach_me.database import migrations
from teach_me.errors import ToolError
from teach_me.server import mcp
from teach_me.tools import create_user, migrate_vault


@pytest.fixture
def one_migration(monkeypatch):
    """Pretends this version of the tools needs one migration, that renames the users."""
    calls = []

    def rename_users():
        calls.append("run")
        return ["users/user-alice.md : renamed"]

    monkeypatch.setattr(migrations, "MIGRATIONS", [rename_users])
    return calls


def test_a_new_vault_gets_the_current_version(vault, one_migration):
    assert migrations.vault_version() == 1
    assert (vault / ".teach-me" / "version").read_text() == "1\n"
    migrations.check_current()


def test_an_old_vault_must_be_migrated(vault, one_migration):
    create_user("Alice", {"language": "english"})  # written without the version file : a vault of version 0
    with pytest.raises(ToolError, match="Call migrate_vault"):
        migrations.check_current()
    result = migrate_vault()
    assert result["from"] == 0 and result["to"] == 1
    assert result["changes"] == ["users/user-alice.md : renamed"]
    assert (vault / result["backup"] / "users" / "user-alice.md").is_file()
    migrations.check_current()
    assert migrate_vault()["changes"] == [] and one_migration == ["run"]  # only once


def test_a_newer_vault_is_refused(vault):
    (vault / ".teach-me").mkdir()
    (vault / ".teach-me" / "version").write_text("7\n")
    with pytest.raises(ToolError, match="newer version"):
        migrations.check_current()


def test_the_server_refuses_an_old_vault(vault, one_migration):
    create_user("Alice", {"language": "english"})

    async def scenario():
        async with Client(mcp) as client:
            refused = await client.call_tool("list_users", {}, raise_on_error=False)
            await client.call_tool("migrate_vault", {})
            users = await client.call_tool("list_users", {})
            return refused, users

    refused, users = asyncio.run(scenario())
    assert refused.is_error and "migrate_vault" in refused.content[0].text
    assert users.data[0]["slug"] == "alice"


def test_the_command(vault, one_migration, capsys):
    create_user("Alice", {"language": "english"})
    assert migrations.main([str(vault)]) == 0
    assert "Migrated from version 0 to 1" in capsys.readouterr().out
    assert migrations.main([str(vault)]) == 0
    assert "nothing to do" in capsys.readouterr().out
