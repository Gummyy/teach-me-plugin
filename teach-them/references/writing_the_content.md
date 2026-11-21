# What to write

Write for a busy teacher who reads a note 10 minutes before using it : the essentials first, then the details. Most notes are read by the students too : what they see, and what goes in a teacher block, is in [the vault layout](vault_layout.md#what-the-students-see). Every note ends with its **related contents** when there are some : the videos, podcasts, articles or people that will make a student (or the teacher !) curious, with the exact section to look at.

## Project

The subject the teams build all along the course, sized for a team of ~4 over the 10 days, working on it alone in the autonomy half days.

- **The pitch** : 3-5 sentences that make the students want to build it.
- **The features** : the minimum the team must deliver, then the bonus features for fast teams.
- **The deliverables** : links to them, with their day.
- **What a great result looks like** : the demo the teacher hopes to see at the end.
- **The roles** : how a team can split the work so that everyone practises every core skill.

## Class

What the teacher presents, ~30-55 minutes, always followed by something the students do. The students read it after the class : the goal, the content and the diagrams are for them, the rest goes in teacher blocks.

- **Goal** : the skills it teaches, in one sentence.
- **Content** : the concepts, in the order the teacher presents them, with diagrams and examples. Explore widely first, describe thoroughly later (see [the teaching reference](../../shared/teaching.md#pedagogical-progression)).
- **Questions to ask the room** : 2-4 questions that keep the students thinking, with the answers you expect (in a teacher block).
- **Surprise** : one example from another field, a fun fact or an unexpected application (in a teacher block, so it stays a surprise).
- **Next** : the activity, quiz or autonomy work that follows.

## Activity

An exercise where the students are active : they discuss, build, explain, compare, predict or play. Vary the formats over the days, for instance think-pair-share, jigsaw, peer instruction, predict then run, live code review between teams, role play, debate, gallery walk, unplugged simulation, escape game, kata.

- **Instructions for the students** : what they do, in which groups, how long, and what they hand in. When the students work through it alone (a lab, a kata), every step they need is here.
- **Goal** : the skills it practises, and why this format fits them.
- **Format** : solo, pairs, teams or the whole group; duration; room and material.
- **Run sheet** : the steps with their timing, what the teacher says and does, what the students do.
- **Debrief** : the questions that turn the activity into learning, and the key points to conclude with.
- **Variations** : shorter, longer, harder, easier, remote.
- **What can go wrong** : the usual blockers and how to unlock them.

Everything after the instructions for the students goes in a teacher block.

## Autonomy

A half day where the teams build their project alone : the teacher isn't there, so write the note for the students.

- **Goal** : what the team must have done by the end, towards which deliverable.
- **Suggested steps** : a rough order of the work, with the time each part should take, and how to split it in the team.
- **Helpers** : links to the cheat sheets, templates and starter code that unlock the usual problems.
- **Stuck ?** : what to try before waiting for the teacher (re-read a class, ask another team, a debugging checklist), and how to note a question for the next activity half day.
- **Team log** : 3-5 lines to write at the end : what was done, what blocks, who did what. The teacher reads them at the next activity half day.

The first autonomy half day comes before the teams have set anything up : its goal includes the setup (accounts, tools, repository, team charter), and the next activity half day opens with a setup corner for the teams still blocked.

## Quiz, deliverable and presentation

Each one is ready to hand out and ready to correct, in 4 sections :

1. **Instructions for the students** : what you'd hand out, ready to copy as is. The context, the questions or the expected work, the format of the answer, the duration (or the deadline), how it is graded.
2. **Expected outcome** : very detailed. For a quiz, the solution of every question. For a deliverable or a presentation, what a great result contains, piece by piece, with an example when it helps (a sample answer, an excerpt of code, a diagram).
3. **Correction** : very detailed. For every question or criterion, its skills, what earns an A, a B, a C or a D (the grades of [the exams reference](../../shared/exams.md#questions-and-grades)), and the mistakes you expect, each with the explanation to give the student. For a deliverable or a presentation, end with a grading grid the teacher can fill in for each team.
4. **Tips to guide the students** : hints from the lightest to the strongest, so the teacher can unlock a team without giving the answer (copy / paste kills learning), and the questions to ask a team that is stuck.

The 4 sections live in the same note : the instructions for the students first, then the 3 other sections in one teacher block. The teacher may postpone the expected outcome and the correction (e.g. until the teams picked their subject) : write a `> [!todo]` callout under their heading instead of the full text, and list it in the review.

### Quizzes

Follow [the quiz guidelines](../../shared/exams.md#quizzes). The recall quiz that opens a day takes 5-10 minutes; it is formative (not graded), unless the teacher says otherwise. Add, for every option of a closed question, why it is right or wrong : the teacher will be asked.

### Deliverables

A deliverable is a milestone of the project, for a team, sized for the autonomy time before its deadline (usually 2-3 half days), and due at the start of an activity half day so the teacher can give feedback. The feedback to each team (~10-15 minutes) runs during that activity half day, one team at a time, while the other teams work on their own : plan an activity in teams, long enough for every team to get its turn. Follow [the project exam guidelines](../../shared/exams.md#project-exams). Vary the formats from one deliverable to the next (code, diagram, report, video, poster, ...). Say how each student's contribution shows, so that every student of the team is evaluated.

### Presentation

The final presentation of each team : ~20 minutes with a demonstration whenever the project allows it, then 15 minutes of questions from the room. With 5 teams, it takes the morning of the last day. Give the teacher the schedule of the session for all the teams, the questions to ask, and a grading grid covering the content, the demo and the presentation itself. Plan a backup when the demo can't run (a recorded video, screenshots).

## Instructions

Tips for the teacher on how to accompany the students (`audience: teacher`) : one note per day the teacher spends with them, plus one per topic that deserves it (team dynamics, a hard concept, the use of AI tools, ...).

The note of a day is the teacher's entry point, read before the day starts : it lists every step of the day, in order, with a link to each.

- **The day at a glance** : its steps and timing, the material to prepare beforehand, and the team logs and deliverables to read before the day starts.
- **What to watch** : the signs that a student or a team is lost, disengaged or overwhelmed, and what to do.
- **The hard moments** : the concepts or steps where students usually struggle, and how to unlock them.
- **Keeping the energy** : when to take a break, change format or tell a story.

## Helpers

Anything that saves time to the teacher or the students : a cheat sheet, a glossary, a template of deliverable, a starter project, a dataset, a checklist, a setup guide. Make each one usable on its own, and set its `audience` : `student` for what the students use, `teacher` for what only the teacher uses. Put its files in `helpers/<slug>/` and describe them in the note : what it is, who uses it, when, and how.
