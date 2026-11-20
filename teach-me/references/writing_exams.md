# Writing exams

Read the exams section of [the teaching reference](../../shared/teaching.md#exams) first : the kinds of questions, the grades, the guidelines for quizzes and project exams, and the target difficulty. This file adds how the `teach-me` tools handle exams.

You are autonomous when it comes to writing the questions. Keep in mind the skills that you are trying to evaluate and the projects on which the student is going to use them.
Each question may evaluate multiple skills of the course (given by their slugs, as in `get_course_state`), and comes with its solution (`correct_options` or `expected_answer`), which the tools keep hidden from the student. The grade of a question counts for each of its skills. The tools write the exam file, propose a grade for the closed questions and compute the grades of the skills, but you are responsible for grading every question, in `correct_exam` !

The grade of a skill is the letter closest to the weighted mean of the grades of all its questions, in every exam of every course : a question of a project exam weighs twice a question of a quiz.

Every exercise follows the same cycle :
1. Write the questions and call `create_exam`, with the slug of its step of the plan as `planned` (and for a project exercise, the project it builds towards).
2. Let the student answer, where the interface makes it easiest (see [Adapt to the interface](../SKILL.md#adapt-to-the-interface)) :
   - **in the chat** (app or browser) : ask the questions in the chat, with an interactive question tool when you have one (single choice for `single`, multiple selection for `multiple`). Never reveal a solution before the student has answered every question.
   - **in the vault** (terminal) : give the student the path of the exam file, ask them to tick their options and to write their open answers there, and to tell you when they're done. Then pull their results from github (they will always push on main) to retrieve the filled exam and call `read_exam`, which returns their answers and the solutions.
3. Get the answers :
   - answered in the chat : call `submit_answers`. The tool writes their answers into the exam file.
   - answered in the vault : call `read_exam`.

   Both return the answers, the solutions and a proposed grade for each closed question, from the options the student ticked (A for the exact answer, then B, C or D as the answer drifts away from it).
4. Call `correct_exam` with the grade of every question, each with an explanation. Give the grade of each open question. For a closed question, leave the grade out to accept the proposal, or change it when the question deserves it. The correction is appended below the exam, which is never rewritten.

   For a long project exam, you can grade the questions in several steps with `grade_questions` (grading a question again replaces its grade), then call `correct_exam` with the remaining ones.
5. Share the result in the chat, briefly : what went well, what to review.

## Project exams

Don't ask too much at once. The student should be able to complete a project exam in less than 30 minutes. In most cases, you have to chain multiple project exercises to fully build a relevant milestone. It is better to split like this, because it encourages to continue advancing where they may have abandoned if you had asked everything at once. If you feel that a project exam should require more work, ask the student if they are ok with it. If, and only if they validate it, you can pose them a bigger challenge !

## Difficulty

The tools propose the grades of the closed questions, but you have to grade the open questions yourself. After each exam, based on the results of the student, the course state's `progress.advice` (returned by `start_session` and `get_course_state`) says whether to keep, raise or lower the difficulty, and when a failed exam needs a re-explanation first. Follow it.
