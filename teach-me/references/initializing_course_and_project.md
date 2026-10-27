# Defining and initializing the projects and courses of a student

The creation of a course follows these steps :

```mermaid
sequenceDiagram
	actor user as Student
	participant teachme@{ type: "control"} as teach-me
	participant vault@{ type: "database"} as Obsidian vault
	
	user->>teachme : Defines project
	teachme->>vault : Calls get_project with a name for the described project
  vault-->>teachme : Returns the list of projects, none of which match the description of the project provided by the user
  teachme->>teachme : Thinks deeply about the description of the new project, asking the student to validate each decision.
	teachme->>vault : Calls create_project to initalize the new project
	teachme-->>user : Validates the new project
	user->>teachme : Defines a course
	teachme->>vault : Calls get_course with a name for the described course
  vault-->>teachme : Returns the list of courses, none of which match the description of the course provided by the user
  teachme->>teachme : Thinks deeply about the description of the new course, asking the student to validate each decision.
	teachme->>vault : Calls create_course to initalize the new course, linking it to the defined project
	teachme-->>user : Validates the new course
	
	user->>teachme : Asks to start the course
	teachme->>teachme : Thinks about the content
	teachme->>user : Teaches
```

We always start by creating the project, then only do we create the course, because the content of the course must adapt to the projects, not the other way around. The order matters a lot, even if it confuses your student. Always start by defining the project(s), then the course(s)

## Initializing a project

In order to initailize a project, you must ask questions to your student until you have the answer to all of these questions :

- what is the current state of their project ? Is it new, already started, almost finished ? Can you read the current version of the project ?
- what does the student want to build ? You must identify precisely the features that they wish to add to their project. This may need a couple questions / answers. Be patient and don't rush this step as it is one of the most defining moments of the time you'll have with your student.
- how are they working on their project ? Do they work alone ? How much time do they plan on allocating working on their project ? You will have to adapt your lessons based on the attachment of the user to their project, as it is the most relevant measurement of their overall involment in your lessons as well.

The answer to all of these questions must be gathered before creating the project. Once they are acquired, call `create_project` with all these info. Don't omit any detail, since your student won't repeat themselve and expect that you've remembered everything.

## Initializing a course

In order to initialize a course, you must ask questions to your student until you have the answer to all of these questions :
- what does the student want to learn ?
- what does the student already know ?
- what is the student's project ? If they have no precise project, propose some examples until they pick one. It is always better if the student likes their project as it is going to be their main source of motivation ! Refer to the [initializing a project](#initializing-a-project) reference !

Then list **all** the skills that the student will validate during this course (it can range from ~5 to ~100), with a one sentence description each, and check the list with the student. The student may not be able to validate the skills because they don't know many of the concepts you are about to teach them, but they must confirm that they believe you have succesfully targeted what they want to learn.

### Determining the skills of a course

Exams can only evaluate the skills declared here, so take your time, as this is a very important step !
Here are the keys to properly choosing the skills associated with a course :
- Evaluate all the relevant concepts. You don't have to create a skill for all the side content / very specific examples you mention during a class, but the core concepts MUST be evaluated at least once.
- Evaluate the most important concepts multiple times. If it is relevant, you can have multiple skills evaluating the same concept with increasing difficulty. Repetition helps students generalize more efficiently and helps them be more confident that they have really validated a skill.
- Define a realistic progression. Your student may have great aspirations but start from a very modest level. Be sure that you accompany them along the way at the cadence that best fits their progression. In most cases, the number of skills shouldn't go past 50, but in some cases, you may need to use much more to properly accompany your student !
- Use skills that matter for the projects. Be driven by the needs of the projects. It is OK if some skills don't relate completely to the course, but it is not OK if some skills don't relate to the projects or if the student can't finish it with your lessons. If there are lots of skills that are essential for the projects which clearly don't belong to the courses, tell the student as they may not realize that they didn't target the appropriate skills for their project. The outcome of that discussion should be either :
    1. you change the definition of the current course / project
    2. you create a new and more suitable course / project
- Go further than the project. If your student can accomplish harder tasks than the project, than they will be more confident that they can build their project. It is therefore advisable to go a bit further so they can practise on harder problems than what their project requires.

#### Example list of skills for a SQL course

1. Simple Select queries
  1. Using the SELECT keyword
  2. Using the FROM keyword
  3. Using the WHERE keyword
2. Select queries on different tables
  1. Understanding the different types of JOIN
  2. Using JOIN with SELECT queries
3. Working with agregation
  1. Using the GROUP BY keyword
  2. Using the HAVING keyword
  3. Using complex queries with agregation

As you can see in that example, the 2.x and 3.x skills imply using the skills developped in the 1.x section. It is ok to repeat these skills because they are important the progression is very natural.

#### Questions to ask yourself before validating the skills of a course

- Do I cover the important concepts of the course ?
- Do I sufficently cover the most important ones ?
- Does the progression feel natural with the current level of the student up until the completion of their projects ?
- Can the student build their projects if they have validated all their skills ?
- Will the student need to validate most of their skills to build their projects ?

Once you have gathered all these info, call `create_course`.