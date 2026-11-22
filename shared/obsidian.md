# Obsidian Flavored Markdown

Read this when the session has no skill about Obsidian markdown : it is the syntax the notes of both skills use. When the session has one, follow it instead.

## Links

- Link a note by its file name, without the folder or the `.md` : `[[skill-convolution]]`, with a display text after a `|` : `[[class-kernels|Kernels]]`.
- Link a heading with `#` : `[[class-kernels#Padding]]`, a heading of the same note with `[[#Padding]]`.
- Embed a note, an image or a view of a base with `!` : `![[schema.png]]`, `![[course.base#Plan]]`.
- Inside a table, escape the `|` of a link : `[[class-kernels\|Kernels]]`.
- Link only notes that exist : the `teach-me` tools refuse a broken link, `teach-vault check` reports one.
- In `teach-me`, link the skills a class teaches (`[[skill-convolution|convolution]]`) and the earlier classes it builds on : the student follows the links from one note to the next.

## Callouts

```markdown
> [!note] Title
> Content, on as many quoted lines as needed.
```

Types : `note`, `info`, `tip`, `success`, `question`, `warning`, `failure`, `danger`, `bug`, `example`, `quote`, `todo`. Add `-` after the type to fold it (`> [!tip]- Hint`), `+` to unfold it. Use them for definitions (`info`), pitfalls (`warning`), hints to unfold (`tip`-) and examples (`example`).

## The rest

- Math : `$x^2$` inline, `$$ ... $$` on their own lines for a block.
- Highlight : `==text==`. Comment, hidden in reading view : `%% text %%`.
- Mermaid : a ` ```mermaid ` block renders in Obsidian (see [the mermaid guide](mermaid.md)).
- A blank line before and after headings, lists, tables, code blocks and callouts.
- Properties (the YAML frontmatter) hold flat values only : texts, numbers, dates, lists of texts or links. In `teach-me`, the tools write them : never write a frontmatter in the content you send them.

## What the tools generate in `teach-me`

Some parts of the notes are written by the tools between `%% teach-me:<name> start %%` and `%% teach-me:<name> end %%` lines : the views of `Home.md` and of the course notes, the history of a skill. Don't copy them into a content. The student writes in the `## ✏️ My notes` section of a note : read it when it matters, never rewrite it.
