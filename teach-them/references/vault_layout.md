# Vault layout

There are no tools for this vault : you write the notes yourself, following this layout, in Obsidian Flavored Markdown. Load the Obsidian and vault conventions skills of the session first (see [Writing in an Obsidian vault](../SKILL.md#writing-in-an-obsidian-vault)).

## Which vault

Write into the teacher's teaching vault. If the working directory is an Obsidian vault (it has a `.obsidian/` folder) and holds a `courses/` folder written by this skill, or is empty, use it. Otherwise, ask the teacher for the folder once, and remember it in the conversation. Never write into a `teach-me` vault (it has a `users/` folder) : it is the memory of a student, managed by the `teach-me` tools.

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

Every note starts with a YAML frontmatter. Quote the wikilinks. Dates use `YYYY-MM-DDTHH:mm`.

| Property | Notes | Value |
| --- | --- | --- |
| `type` | all | `course`, `project`, `skill`, `class`, `activity`, `quiz`, `autonomy`, `deliverable`, `presentation`, `instructions` or `helper` |
| `course` | all but projects and skills | `"[[course-<course>]]"` |
| `created_at`, `updated_at` | all | dates |
| `skills` | steps, helpers | list of `"[[skill-<skill>]]"` |
| `day` | steps | `1` to `10`, the day it happens (or fits best, for a proposed activity) |
| `half_day` | steps | `morning` or `afternoon` |
| `date` | steps | `YYYY-MM-DD`, once the teacher gave the calendar |
| `duration` | steps | minutes, e.g. `45` |
| `importance` | steps | `core` or `optional` |
| `status` | steps, helpers | `proposed`, `chosen` or `dropped` |
| `projects` | course, deliverables, presentation | list of `"[[project-<project>]]"` |
| `group` | course | `students`, `team_size`, `activity_days`, `autonomy_days`, `deliverables`, `presentation`, `dates` (the list of the days, when known) |

A step is a class, an activity, a quiz, an autonomy, a deliverable or a presentation. Classes, autonomy half days, exams and helpers are `chosen` from the start; activities stay `proposed` until the teacher picks them.

## The course note

`course-<course>.md` is the entry point of the teacher :

1. **Context** : the subject, the group (level, what they know, equipment), the settings of the group and the calendar.
2. **Projects** : links to the project notes and the deliverables, with their day.
3. **Skills** : links to the skill notes, grouped by section, as in [designing a course](../../shared/designing_a_course.md#choosing-the-skills-of-a-course).
4. **Plan** : a table of every step, half day by half day.

   | Day | Half day | Step | Type | Duration | Description | Skills | Status |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | 1 | morning | [[class-...\|Title]] | 📖 class | 30 | ... | [[skill-...\|...]] | chosen |

   Escape the `|` of an alias inside a table with `\|`. Icons : 📖 class, 🤸 activity, ❓ quiz, 🧭 autonomy, 📦 deliverable, 🎤 presentation. Write the date in the Day column once it is known.
5. **Extra activities** : the `proposed` activities, to pick from.
6. **Instructions and helpers** : links to them.

Keep the course note in sync : when a step is added, moved, chosen or dropped, update its row.
