# Mermaid guide

## Choosing the diagram

When describing the relationships between different types of entities, you may use `flowchart`.
When describing chronology, you may use `timeline` with a few relevant bullet points (over 6 is probably a mistake).
When modelling data, you may use `erDiagram`.
When modelling Object Oriented Programming, you may use `classDiagram`.
When describing a planning, you may use `gantt`.
When presenting data, you may use either `pie` or `xychart-beta`. Explicitly let the student know that the exact values you display may be wrong, but propose a way to find the accurate values, using either a link or a specific web search (having the student do the search on their own may be beneficial to build familiarity with the overall context of their search). As long as the student is warned, feel free to propose projections or simulated data to make the relationship between x and y visual.

## Consistent declarations and ordering of items

Be consistent when using ordered relationships, to help the mermaid engine render a coherent diagram. *For instance :* if you have used `Animal --> Dog`, you must use `Dog --> Corgi` instead of `Corgi <-- Dog`.

Before writing the whole diagram, think about these :
- what shape is more appropriate to each type of entity ? Most important entities must be more visible and some shapes naturally match certain concepts (circles for living beings, squares for stable elements, database for database, human actor for user, ...)
- what relationships are labeled ? If some labels are more important, you may decide to remove all other labels to emphasize the important ones. Over 6 different labels is most likely a mistake, but you can have many occurrences of the same label.
- what piece of information belongs to the name of each entity ? It is always possible to add additional data (like example values (probably belongs to a different node), additional properties (depends)). You can either put these informations in the name of the entity, in a related node or skip it entirely.

Once a shape is chosen, use it consistently in all the remaining entities of the remaining diagrams. If you have chosen a specific rule for naming, it must be consistent throughout your other entities and diagrams as well.

Entities names always start with a capital. Labeled relationships are always displayed in lowercase.
