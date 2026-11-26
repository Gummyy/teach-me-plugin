# teach-me-mcp

MCP server handling the persistent memory of the `teach-me` skill. The memory is an Obsidian vault : a folder of markdown files whose structured data lives in the frontmatter.

```
vault/
├── Home.md                            # the entry point : the views of every course (bases/home.base)
├── bases/course.base, bases/home.base # the Obsidian bases embedded in Home.md and in the course notes
├── users/user-<user>.md
├── projects/project-<project>.md
├── skills/skill-<skill>.md            # owned by a user, shared by their courses : its grade in its properties, its history in its body
├── .teach-me/                         # hidden from Obsidian : exam data, the version of the vault, backups and the lock
└── courses/<course>/
    ├── course-<course>.md             # links to its skills and projects, the views of the course (bases/course.base), the student's notes and the session log
    ├── classes/class-<class>.md       # a step of the plan : created as planned, filled by save_class
    ├── resources/resource-<resource>.md  # a shared resource : its link and status, the student's notes
    └── exams/quiz-<exam>.md           # or exercise-<exam>.md for a project exam : questions, solutions and grades in .teach-me/
```

Every note has an `id` property, its file name when the tools created it (`skill-convolution`), and a `type` property (`user`, `project`, `skill`, `course`, `class`, `quiz`, `exercise`, `resource` or `home`), and the notes of a course a `course` property linking to it, so that Obsidian Bases can select them.

Properties are flat (text, numbers, dates, lists of links) : Obsidian's property panel shows a nested value as raw JSON, and Bases can't read it. What only the tools need (the questions of an exam, its solutions, the grades of its questions and skills) is in `.teach-me/exams/`, `.teach-me/solutions/` and `.teach-me/grades/`.

The hidden data of an exam (`.teach-me/exams/<exam>.json` : its type, questions, grades and `corrected_at`) is its **source of truth**. The `type`, `status`, `mean`, `questions` and `skills` of the exam note, and the `grade`, `score`, `evaluations`, `last_evaluated`, `progression` and history of the skill notes, only show it : the tools never read a grade from a note, and `start_session` writes these values again when the student changed them by hand.

The tools write some parts of a note themselves, between `%% teach-me:<name> start %%` and `%% teach-me:<name> end <hash> %%` (hidden in reading view), and rewrite them when their data changes. The rest of the note belongs to the student. When the student edited a generated part, their version moves to the `## ✏️ My notes` section of the note before the part is rewritten.

Obsidian finds a note by its file name, wherever it is : the prefix of each kind keeps file names unique in the vault, so every link points to exactly one note. The tools only take slugs, without the prefix. Dates live in the frontmatter (`created_at`, and `started_at` once a step was given). Each step of the plan of a course is a note from the moment it is planned : its `order`, `status` (`planned`, then `new` and `read` for a class, `assigned`, `filled`, `corrected` for an exam), `description`, `skills` and `importance` are its properties, and `bases/course.base` shows them in the course note.

A note broken by hand never stops the tools : the lists and views skip a note they can't read, a list property typed as a single text is read as a list of one, and a link to a deleted note is kept as it is. The tools then work without it, and add what they skipped to their result as `vault_warnings`, for the model to fix. Only a tool asked for that very note fails, with the way to repair it.

A note the student renamed or moved in Obsidian is put back by `start_session`, under the name and in the folder its `id` gives (`teach_me/database/renames.py`) : the tools find notes, and the hidden data of an exam, by their file name. The links that Obsidian changed to the new name point to the note again, and the name the student gave is kept in the `aliases` property, so that the quick switcher still finds the note by it. A copy (same `id` as a note in its place) is left alone, with a warning.

Every file is written atomically (a temporary file renamed over it), so a crash never leaves half a note or half a JSON file. A file holding git merge conflict markers, or a JSON file that can't be read, gives an error naming it and how to restore it.

The vault path is read from the `TEACH_ME_VAULT` environment variable (a relative path is relative to the working directory). The folder is created if it doesn't exist.

## Code layout

| Path                           | Content                                                                |
| ------------------------------ | ---------------------------------------------------------------------- |
| `teach_me/server.py`           | The FastMCP server : registers the tools. `main()` is the `teach-me-mcp` command |
| `teach_me/tools/`              | The 28 tools, as plain functions (docstrings are what the model reads), run one at a time under the lock of the vault |
| `teach_me/database/vault.py`   | Markdown files, frontmatter, slugs, checked links, time                |
| `teach_me/database/objects.py` | Where each object lives in the vault, course content, session log, skill grades |
| `teach_me/database/blocks.py`  | The parts of a note the tools generate, and the student's "My notes" section where their edits of a generated part move |
| `teach_me/database/plan.py`    | The plan of a course : the notes of its steps                          |
| `teach_me/database/renames.py` | The notes renamed or moved in Obsidian, put back where their `id` says |
| `teach_me/database/dashboards.py` | The Obsidian bases of the vault, and the views at the top of the course notes. `tests/test_dashboards.py` checks their structure, but only Obsidian tells whether a view renders : see below |
| `teach_me/database/quiz.py`    | Exam files, answers, the A-E grades                                    |
| `teach_me/database/migrations.py` | The version of the vault and the migrations to the current format. `main()` is the `teach-me-migrate` command |
| `teach_me/database/migration_<n>.py` | What migration `n` changes in the notes of a vault at version `n - 1` |
| `teach_me/vault/`              | The `teach-vault` command of the `teach-them` skill, and the frontmatter and wikilink parsing shared with the tools |
| `tests/`                       | pytest suite, each test runs in a temporary vault                      |
| `server.py`                    | Runs the server without installing it : `python server.py`             |

## Run the tests

With uv :

```bash
cd teach-me-mcp
uv run pytest
```

Or with a venv :

```bash
python -m pip install -r requirements.txt
python -m pytest
```

## Migrations

When a new version changes the format of the notes, it adds a function to `MIGRATIONS` in `teach_me/database/migrations.py`. The version of a vault is in `.teach-me/version` : the tools refuse an older vault and ask the model to call `migrate_vault`, which backs up the notes, the bases and `Home.md` into `.teach-me/backups/<date>/` and runs the missing migrations. Migration `n` lives in `teach_me/database/migration_<n>.py`. You can also run them yourself :

```bash
uv run teach-me-migrate /path/to/the/vault
```

## Check the views in Obsidian

A base can be valid YAML and still not render. With Obsidian running and a migrated vault open, `scripts/query_base.sh` prints what each view returns, or the error Obsidian shows :

```bash
scripts/query_base.sh <vault name> <vault folder> bases/course.base courses/<course>/course-<course>.md
```

`this` is bound to the note given, as when the view is embedded in it. The display names and the summaries only show in the rendered note.

## The `teach-vault` command

The vault scripts of the `teach-them` skill, whose vault the model writes itself (no tools) :

```bash
uv run teach-vault plan <vault> [--check]               # rebuild the plan, extra activities and skills coverage tables of the course notes
uv run teach-vault check <vault>                        # links, skills evaluated, daily recalls, exam sections, teacher links
uv run teach-vault export <vault> <destination> [--force]  # the student vault, then its link checks
```

The plugin's hooks run `plan` and `check` at the end of each turn that edited a `teach-them` vault (see [hooks/hooks.json](../hooks/hooks.json)).

## Try the tools by hand

The MCP Inspector calls the tools without any LLM (needs Node.js). The Inspector doesn't pass your shell's environment to the server, so give it the vault with `-e` :

```bash
npx @modelcontextprotocol/inspector -e TEACH_ME_VAULT="$TEACH_ME_VAULT" uv run --project . teach-me-mcp
```

## Run it

The plugin starts the server for you (see the [main README](../README.md)). To declare it by hand in an MCP client, the command is :

```bash
uv run --project /path/to/teach-me-mcp teach-me-mcp                                   # from a clone
uvx --from "git+https://github.com/Gummyy/teach-me-plugin#subdirectory=teach-me-mcp" teach-me-mcp  # from GitHub
```

with `TEACH_ME_VAULT` set in the server's environment, for example :

```bash
claude mcp add teach-me --env TEACH_ME_VAULT=/path/to/the/vault -- uv run --project /path/to/teach-me-mcp teach-me-mcp
```
