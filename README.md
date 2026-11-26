# teach-me

A Claude Code plugin with two skills :

- `teach-me` turns Claude into a teacher who remembers you : classes, quizzes, project deliverables and a report card, kept in your own Obsidian vault. Open `Home.md` in the vault to see where you are : your courses, exams to answer, deliverables in progress, resources to look at, skills to work on and projects; each project note shows the courses and skills that work on it, and what you built for it (Obsidian 1.9+ for the Bases views, 1.14+ for the resources board).
- `teach-them` turns Claude into the teaching partner of a teacher : it prepares a course for a group of students (classes, active learning activities, team project deliverables, exams with detailed corrections, tips for the teacher and practical helpers), written as an Obsidian vault.

| Path                       | Content                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| `teach-me/`                | The skill : teaching one student, through the MCP tools              |
| `teach-them/`              | The skill : preparing a course for a teacher, written in the vault   |
| `shared/`                  | The references shared by the skills : pedagogy, course design, exams, diagrams, Obsidian markdown |
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

Claude Code asks for the folder of your vault when the plugin is enabled (you can change it later in `/config`). Then ask Claude to teach you something, or to prepare a course for your students. `teach-them` writes the notes itself (no MCP tools) : give it the folder of your teaching vault, separate from your `teach-me` vault.

To update after new commits : `/plugin marketplace update gummyy`.

## Develop

Load the plugin from your clone instead of installing it, so that your changes apply at the next start :

```bash
claude --plugin-dir /path/to/teach-me-plugin
```

Check the manifests with `claude plugin validate /path/to/teach-me-plugin`. The plugin's [hooks](hooks/hooks.json) serve `teach-them` : after a turn that edited a `teach-them` vault, they rebuild its plan and check it with `teach-vault` (they exit at once for any other file). The server has its own [README](teach-me-mcp/README.md) (tests, MCP Inspector).

## Use it in cloud sessions and on your phone

Cloud sessions (claude.ai/code, the Code tab of the mobile app, **Cloud** in the Desktop app) clone **one** repository and don't load plugins. So the vault repository carries what the session needs :

```bash
python scripts/setup_vault.py /path/to/your/vault
```

writes into the vault :

- `.claude/skills/teach-me/` and `.claude/skills/shared/` : a copy of the skill and of its shared references (run the script again after changing them)
- `.mcp.json` : the MCP server, installed from this repository with `uvx`
- `.claude/settings.json` + `.claude/hooks/sync_vault.sh` : at the end of each turn of a cloud session, commits the vault and pushes it to `main`, otherwise the session's changes would be lost with its machine
- `CLAUDE.md` : tells Claude what the vault is

Commit and push these files, then start a cloud session on the vault repository.

> [!Note] On your own computer
> When you open Claude Code **inside** the vault with the plugin installed, the skill and the server are loaded twice (plugin + vault). Decline the vault's `.mcp.json` server when Claude Code asks, or work from another folder.
