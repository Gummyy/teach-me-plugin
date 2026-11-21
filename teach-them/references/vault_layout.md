# Vault layout

There are no tools for this vault : you write the notes yourself, following this layout, in Obsidian Flavored Markdown. Load the session's skill about Obsidian Markdown and the skills about the user's own vaults or note conventions first; the others (bases, canvas, ...) only when you write that kind of file (see [Writing in an Obsidian vault](../SKILL.md#writing-in-an-obsidian-vault)).

## Which vault

Write into the teacher's teaching vault : the folder the teacher names, or else the working directory or one of its subfolders when it is an Obsidian vault (it has a `.obsidian/` folder, e.g. `course/` inside a git repository) holding a `courses/` folder written by this skill, or is empty. Otherwise, ask the teacher for the folder once, and remember it in the conversation. Every path of this layout is relative to that folder. Never write into a `teach-me` vault (it has a `users/` folder) : it is the memory of a student, managed by the `teach-me` tools.

## Folders and files

```
projects/project-<project>.md
skills/skill-<skill>.md
courses/<course>/course-<course>.md
courses/<course>/classes/class-<slug>.md
courses/<course>/activities/activity-<slug>.md
courses/<course>/autonomy/autonomy-<slug>.md
courses/<course>/exams/quiz-<slug>.md
courses/<course>/exams/deliverable-<slug>.md
courses/<course>/exams/presentation-<slug>.md
courses/<course>/instructions/instructions-<slug>.md
courses/<course>/helpers/helper-<slug>.md
courses/<course>/helpers/<slug>/...              (the files of a helper : code, data, templates)
```

- A slug is lowercase ASCII words separated by `-`, at most 50 characters, e.g. `sql-joins-in-a-nutshell`.
- Obsidian finds a note by its file name, wherever it is : the prefix keeps file names unique in the whole vault, so **check that the file name is free** before writing a new note, and add a short suffix when it isn't.
- Link notes with wikilinks, without the folder : `[[class-sql-joins-in-a-nutshell|SQL joins in a nutshell]]`.
- Never delete a note the teacher may have edited : set its `status` to `dropped` instead.

## Properties

Every note starts with a YAML frontmatter. Quote the wikilinks. For the dates, use the vault's own date properties and format when it has some (e.g. `creation_time`, `YYYY-MM-DD HH:mm`), otherwise `created_at` and `updated_at`, as `YYYY-MM-DDTHH:mm`. Every property is flat (no nested values) : Obsidian's property panel shows a nested one as raw JSON.

| Property | Notes | Value |
| --- | --- | --- |
| `type` | all | `course`, `project`, `skill`, `class`, `activity`, `quiz`, `autonomy`, `deliverable`, `presentation`, `instructions` or `helper` |
| `course` | all but projects and skills | `"[[course-<course>]]"` |
| `created_at`, `updated_at` | all | dates (or the vault's own date properties) |
| `description` | steps, helpers | one sentence, shown in the plan and the extra activities |
| `section` | skills | the section of the skill, as in the course note, e.g. `"1 · Simple Select queries"` |
| `skills` | steps, helpers | list of `"[[skill-<skill>]]"` |
| `day` | steps | `1` to `10`, the day it happens (or fits best, for an extra activity) |
| `half_day` | steps | `morning`, `afternoon`, or `day` for a step that fills the whole day |
| `order` | steps | `1`, `2`, ... : the position of the step in its half day |
| `date` | steps | `YYYY-MM-DD`, once the teacher gave the calendar |
| `duration` | steps | minutes, e.g. `45` |
| `importance` | steps | `core` or `optional` |
| `status` | steps, helpers | `proposed`, `chosen` or `dropped` |
| `audience` | all | `student` or `teacher` : who may see the note (see [What the students see](#what-the-students-see)) |
| `projects` | course, deliverables, presentation | list of `"[[project-<project>]]"` |
| `students`, `team_size`, `students_level` | course | the group : e.g. `20`, `4`, `beginner`, `intermediate` or `advanced` |
| `half_day_hours`, `activity_half_days`, `autonomy_half_days` | course | the calendar : e.g. `3`, `12`, `8` |
| `deliverables` | course | the number of deliverables, e.g. `3` |
| `dates` | course | the list of the days, `YYYY-MM-DD`, once known |

A step is a class, an activity, a quiz, an autonomy, a deliverable or a presentation. The steps you put in the plan are `chosen`, the extra activities are `proposed`, and helpers are `chosen` from the start. The teacher drops what they don't want (`dropped`) and picks an extra by setting it to `chosen`. You set `chosen` yourself only when the teacher validated it in the conversation.

## What the students see

Every note says who may see it with its `audience` property. A student note keeps the parts for the teacher between two lines, `%% teacher:start %%` and `%% teacher:end %%` : Obsidian hides these comments in reading view, and the student version of the course leaves the block out.

| Object | The students see |
| --- | --- |
| Course | the note, without its teacher blocks |
| Project, skill, autonomy | the whole note |
| Class | the content and the diagrams; the expected answers, the surprise and the notes for the teacher go in teacher blocks |
| Activity | the instructions for the students; the run sheet, the debrief and the rest go in a teacher block |
| Quiz | the instructions, handed out on the day; the 3 other sections go in a teacher block |
| Deliverable, presentation | the instructions; the 3 other sections go in a teacher block |
| Instructions | nothing : `audience: teacher` |
| Helper | as each one says, with its `audience` |

A student note links to a teacher note only inside a teacher block.

## The course note

`course-<course>.md` is the entry point of the teacher :

1. **Context** : the subject, the group (level, what they know, equipment), the settings of the group and the calendar.
2. **Projects** : links to the project notes and the deliverables, with their day.
3. **Skills** : the skills coverage table, generated between `%% skills:start %%` and `%% skills:end %%` : every skill note, grouped by its `section`, with the steps that teach it and the exams that evaluate it.
4. **Plan** : the table of the `chosen` steps, half day by half day, generated between `%% plan:start %%` and `%% plan:end %%`.
5. **Extra activities** : the table of the `proposed` activities, to pick from, generated between `%% extras:start %%` and `%% extras:end %%`.
6. **Instructions and helpers** : links to them, the instructions inside a teacher block.

Write the markers, each on its own line, and leave the blocks empty : `teach-vault plan` fills them from the properties of the notes (see [the vault scripts](#the-vault-scripts)). Never edit a generated table by hand, change the properties of the notes instead.

## The vault scripts

The `teach-vault` command of this plugin works on a vault given as its argument :

```bash
uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}/teach-me-mcp" teach-vault plan <vault>                 # rebuild the generated tables
uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}/teach-me-mcp" teach-vault check <vault>                # what fails : links, skills evaluated, recalls, exam sections, teacher links
uv run --quiet --project "${CLAUDE_PLUGIN_ROOT}/teach-me-mcp" teach-vault export <vault> <destination> # the student version, then its links checked
```

- **Continuing a course** : run `plan` before reading the course note, since the teacher may have changed the notes in Obsidian.
- **The student version** : run `export` when the teacher asks for it, into a folder the teacher names, never inside the teacher's vault.

Keep the course note in sync : when a step is added, moved, chosen or dropped, update its row.
