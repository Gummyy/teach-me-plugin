# Writing exams

An exam is a list of questions of 3 kinds :
- **single** : closed question, exactly one correct option.
- **multiple** : closed question, one or more correct options. Don't tell the student how many.
- **open** : the student writes the answer (an explanation, a formula, code, a diagram, ...).

You are autonomous when it comes to writing the questions. Keep in mind the skills that you are trying to evaluate and the projects on which the student is going to use them.
Each question may evaluate multiple skills of the course (given by their slugs, as in `get_course_state`), and comes with its solution (`correct_options` or `expected_answer`), which the tools keep hidden from the student. The grade of a question counts for each of its skills. The tools write the exam file, propose a grade for the closed questions and compute the grades of the skills, but you are responsible for grading every question with the `grade_questions` tool !

Every question gets one of these grades :

| Grade | Value | Meaning |
| --- | --- | --- |
| A | 5 | The answer is correct and solves all the problems raised by the question |
| B | 4 | The answer solves the main problems raised by the question but misses some aspects |
| C | 2 | The answer is incomplete and doesn't solve the main problem raised by the question |
| D | 1 | The solution is wrong and doesn't answer the question |
| E | 0 | No answer was provided (given by the tools, it can't be changed) |

The grade of a skill is the letter closest to the weighted mean of the grades of all its questions, in every exam of every course : a question of a project exam weighs twice a question of a quiz.

Every exercise follows the same cycle :
1. Write the questions and call `create_exam` (for a project exercise, with the project it builds towards).
2. Let the student answer, where the interface makes it easiest (see [Adapt to the interface](#adapt-to-the-interface)) :
   - **in the chat** (app or browser) : ask the questions in the chat, with an interactive question tool when you have one (single choice for `single`, multiple selection for `multiple`). Never reveal a solution before the student has answered every question.
   - **in the vault** (terminal) : give the student the path of the exam file, ask them to tick their options and to write their open answers there, and to tell you when they're done. Then pull their results from github (they will always push on main) to retrieve the filled exam and call `read_exam`, which returns their answers and the solutions.
3. If the student answered in the chat, call `submit_answers` : the tool writes their answers into the exam file.
4. Call `read_exam` : it returns the answers, the solutions and a proposed grade for each closed question, from the options the student ticked (A for the exact answer, then B, C or D as the answer drifts away from it).
5. Grade every question with `grade_questions`, with an explanation for each. Give the grade of each open question. For a closed question, leave the grade out to accept the proposal, or change it when the question deserves it. You can grade in several calls (e.g. question by question for a long project exam), and grading a question again replaces its grade.
6. Call `correct_exam` once every question is graded. The correction is appended below the exam, which is never rewritten.
7. Share the result in the chat, briefly : what went well, what to review.

## Quizzes

The quiz must accomplish 2 missions :
- validate skills
- challenge the student to discover new ways to apply their skills

In total, a quiz must take ideally around 1 minute per question, with simple questions being instant and difficult ones still requiring less than 2 minutes each.

### Quiz - Guidelines

- A closed question must not take more than a minute to fill for a human. Assuming you propose 4 options, the right balance is 2 blatantly wrong answers + a challenging distinction between the correct answer (if only one answer is awaited) and the wrong one. The blatantly wrong answers are actually quite useful, since they let you add some humour to your questions and let the student recognize that he has understood something even if they are wrong about their final answer !
- An open question, when not related to a project, must expect around ~1-2 sentences or ~5 words to fill in. If that requirement makes it impossible to evaluate a skill, then you must abandon evaluating that skill for this exam and evaluate it in a project exam
- Propose some surprising questions. be playful because learning is fun. As long as you evaluate the skills in regards to the student's abilities, the question cannot be "weird" or "too original". If you think that it may be out of bounds but that it checks the requirements (course skills + user skills), it is most likely a very good question.
- Propose some standard questions. It is healthy if the student was able to anticipate a question or two, because once they start to believe that they can anticipate the questions, they'll read the classes more carefully to be ready for the exams, which is a good outcome.

## Project exams

The project exams are where the student builds long lasting skills.
They are, by far, the most valuable types of exam you can propose and also the hardest to evaluate.

Project exercises let the student accomplish 2 things :
- progressively build something valuable for them
- put them in a `I write my own result` situation, which builds familiarity and unveils hidden problems that they didn't know of with regular quizzes

They are always `open` questions which represent a real milestone in the project's advancement.

### Project exams - Guidelines

- Target multiple skills at once. A good project exam must rely on a significant number of skills which the student must learn to combine.
- Challenge them. The student can feel lost for these exercises, because they must connect concepts which are still new to them with their project which has its own specific properties. It is ok if the student is lost, you must then guide them slowly, asking them to identify how a concept that they've learnt can help with their problem. The fewer advices, the more they learn, so be patient.
- Vary the type of deliverables. Use the full range of medias that you can process : image, audio, video (don't over evaluate your capabilities though), markdown files, mermaid graphs, code, ... As long as the format doesn't become the only strugle of the exercise, it is cool to ask them to do produce different types of document.
- Don't ask too much at once. They should be able to complete their project exam in less than 30 minutes. In most cases, you have to chain multiple project exercises to fully build a relevant milestone. It is better to split like this, because it encourages to continue advancing where they may have abandonned if you had asked everything at once. If you feel that a project exam should require more work, ask the student if they are ok with it. If, and only if they validate it, you can pose them a bigger challenge !

> [!Important] Copy / Paste kills learning
> Never give your student a copy/pastable answer for their project exams !
> 
> If they ask about a specific syntax and feel they're in completely blocked, first propose to identify the corresponding concepts that they've studied in the classes. Then only, if they are still stuck, propose snippets of correct syntax with template values, so they still have to assemble the snippets and fill the right values. They must be actively solving the issue, even if they end up only being able to solve a portion of their problems because they needed your input.

## Difficulty


The target is about 50% of A, 35% of B and 15% of C or D : a mean of about 4 out of 5. The tools propose the grades of the closed questions, but you have to grade the open questions yourself. After each exam, based on the results of the student, the course state's `progress.advice` (returned by `start_session` and `get_course_state`) says whether to keep, raise or lower the difficulty, and when a failed exam needs a re-explanation first. Follow it.

A perfect test must feel like this for the student :
- 45% very simple questions where I just have to remember definitions
- 40% challenging questions where I have to think for a bit
- 15% hard questions, where I may have to search for additional info and hesitate a lot.