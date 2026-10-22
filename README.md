# teach-me

A Claude Code plugin that turns Claude into a teacher who remembers you : classes, quizzes, project exercises and a report card, kept in your own Obsidian vault.

| Path                       | Content                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| `teach-me/`                | The skill : pedagogy, diagrams, evaluation (`SKILL.md` + references) |
| `teach-me-mcp/`            | The MCP server : the memory of the teacher, stored in the vault      |
| `.claude-plugin/`          | The plugin manifest and the marketplace that lists it                |
| `scripts/setup_vault.py`   | Makes a vault usable in cloud sessions (see below)                   |

## Install

Requirements : [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs and runs the MCP server for you, and a folder for your vault (ideally a git repository).

In Claude Code :

```
/plugin marketplace add Gummyy/teach-me-plugin
/plugin install teach-me@gummyy
```

Claude Code asks for the folder of your vault when the plugin is enabled (you can change it later in `/config`). Then ask Claude to teach you something.

To update after new commits : `/plugin marketplace update gummyy`.

## Develop

Load the plugin from your clone instead of installing it, so that your changes apply at the next start :

```bash
claude --plugin-dir /path/to/teach-me-plugin
```

Check the manifests with `claude plugin validate /path/to/teach-me-plugin`. The server has its own [README](teach-me-mcp/README.md) (tests, MCP Inspector).

## Use it in cloud sessions and on your phone

Cloud sessions (claude.ai/code, the Code tab of the mobile app, **Cloud** in the Desktop app) clone **one** repository and don't load plugins. So the vault repository carries what the session needs :

```bash
python scripts/setup_vault.py /path/to/your/vault
```

writes into the vault :

- `.claude/skills/teach-me/` : a copy of the skill (run the script again after changing the skill)
- `.mcp.json` : the MCP server, installed from this repository with `uvx`
- `.claude/settings.json` + `.claude/hooks/sync_vault.sh` : at the end of each turn of a cloud session, commits the vault and pushes it to `main`, otherwise the session's changes would be lost with its machine
- `CLAUDE.md` : tells Claude what the vault is

Commit and push these files, then start a cloud session on the vault repository.

> [!Note] On your own computer
> When you open Claude Code **inside** the vault with the plugin installed, the skill and the server are loaded twice (plugin + vault). Decline the vault's `.mcp.json` server when Claude Code asks, or work from another folder.
