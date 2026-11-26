# Writing exams

Read [the exams reference](../../shared/exams.md) first : the kinds of questions, the grades, the guidelines for quizzes and deliverables, and the target difficulty. This file adds how the `teach-me` tools handle them.

There are two kinds of exams, with two very different intentions :
- **quizzes** (`create_exam`) : quick questions, answered in one sitting, that validate what the student learnt and surprise them.
- **deliverables** (`create_deliverable`) : the milestones of a project, that the student builds on their own over several sessions, with a check-in at each session. At the end, they have something worth putting on their resume.

The grade of a skill is the letter closest to the weighted mean of the grades of all its questions, in every exam of every course : a milestone of a deliverable weighs 3 questions of a quiz, so that the deliverables hold a large share of the grades.

## Quizzes

You are autonomous when it comes to writing the questions. Keep in mind the skills that you are trying to evaluate and the projects on which the student is going to use them.
Each question may evaluate multiple skills of the course (given by their slugs, as in `get_course_state`), and comes with its solution (`correct_options` or `expected_answer`), which the tools keep hidden from the student. The grade of a question counts for each of its skills. The tools write the quiz file, propose a grade for the closed questions and compute the grades of the skills, but you are responsible for grading every question, in `correct_exam` !

Every quiz follows the same cycle :
1. Write the questions and call `create_exam`, with the slug of its step of the plan as `planned`.
2. Let the student answer, where the interface makes it easiest (see [Adapt to the interface](../SKILL.md#adapt-to-the-interface)) :
   - **in the chat** (app or browser) : ask the questions in the chat, with an interactive question tool when you have one (single choice for `single`, multiple selection for `multiple`). Never reveal a solution before the student has answered every question.
   - **in the vault** (terminal) : give the student the path of the quiz file, ask them to tick their options and to write their open answers there, and to tell you when they're done. Then pull their results from github (they will always push on main) to retrieve the filled quiz and call `read_exam`, which returns their answers and the solutions.
3. Get the answers :
   - answered in the chat : call `submit_answers`. The tool writes their answers into the quiz file.
   - answered in the vault : call `read_exam`.

   Both return the answers, the solutions and a proposed grade for each closed question, from the options the student ticked (A for the exact answer, then B, C or D as the answer drifts away from it).
4. Call `correct_exam` with the grade of every question, each with an explanation. Give the grade of each open question. For a closed question, leave the grade out to accept the proposal, or change it when the question deserves it. The correction is appended below the quiz, which is never rewritten. Give a short `comment` for each evaluated skill : it shows in the correction and in the history of the skill, in its note.

   For a long quiz, you can grade the questions in several steps with `grade_questions` (grading a question again replaces its grade), then call `correct_exam` with the remaining ones.
5. Share the result in the chat, briefly : what went well, what to review.

## Deliverables

A deliverable runs alongside the course : the classes and the quizzes go on while the student builds it, and it never blocks them. A course has one deliverable at a time, on one of its projects (several courses may each have one on the same project). The course state gives it in `active_deliverable`, and `progress.advice` says when a check-in is due.

1. **Prepare it with the student.** Choose its difficulty from `progress.advice` (the deliverables have their own track, see `last_deliverable`) and from the student's autonomy. Decompose the project into milestones, each due by a check-in (`target_session`), and choose the number of sessions (`max_sessions`). Write the criteria the student checks their work against, the expected outcome and the hints (both hidden), and the `outcome` : what they will have at the end. Present the roadmap in a few lines, then call `create_deliverable` with `planned`. Give the student the path of its note : they work in their project, tick the criteria and write under "Your work" what they did (links to their files or commits, screenshots, what blocked them).
2. **Check in at each session**, once the student showed their work. Ask them to **show** it : the files, the repo, a demo. Never take "it's done" as a proof. Call `read_deliverable`, look at what they point to, then call `checkin_deliverable` :
   - give a comprehensive `feedback` on each milestone they worked on : what works, what to improve and how they can check it themselves. The grades only come at the end : this feedback is how they improve from one session to the next.
   - give a hint (`hints`) only when they are stuck after trying, the lightest first. It never lowers the grade, so never make them feel it costs them anything.
   - set the `next_goals` : what they do on their own before the next session. Remind them at the end of the session.
   - when a milestone turns out too big or too small, move it to another check-in (`reschedule`) rather than letting the student drown.

   Several check-ins in the same session count as one session. The check-ins are logged in the course and in the project automatically.
3. **Grade it once** every session is used (its status is then `submitted`) or every milestone is done. When the student needs more time, propose one extension (`extend`, once at most, with their agreement). Then call `read_deliverable`, look at the work, and call `correct_deliverable` with the grade of every milestone against its expected outcome : `abandoned` for a milestone the student didn't work on (no grade, it counts for no skill). When at least half of the milestones are abandoned, the deliverable is abandoned. Write the `showcase` with the student : what they built, in one or two sentences for their resume.
4. Share the result in the chat : what they built, what they mastered, what to work on next. Call `report_card` : it lists the deliverables with what the student built.

When a deliverable is abandoned or the student loses interest, ask them why in one sentence and log it : the next one should fit them better.

A vault from an older version may hold planned deliverables that were short project exercises before (migration 6). When the plan has several small deliverables in a row for the same project, propose to the student to merge them into one deliverable with a few milestones, with `edit_course` (remove the small steps, add one deliverable step).

## Difficulty

The tools propose the grades of the closed questions, but you have to grade the open questions and the milestones yourself. After each quiz and each deliverable, based on the results of the student, the course state's `progress.advice` (returned by `start_session` and `get_course_state`) says whether to keep, raise or lower the difficulty of the next one, on two separate tracks, and when a failed quiz needs a re-explanation first. Follow it.
