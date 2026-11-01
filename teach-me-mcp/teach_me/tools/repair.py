"""Repairing the notes that the tools can't read anymore."""

from teach_me.database import vault


def repair_note(path: str, frontmatter: str) -> dict:
    """Repairs a note whose frontmatter isn't valid YAML anymore, usually after a manual edit in Obsidian. The tools reading it then fail with an error that gives its path and its current frontmatter : send that frontmatter back, fixed, keeping every key and value. The content of the note is kept as it is.

    Args:
        path (str): The path of the note relative to the vault, as given in the error
        frontmatter (str): The fixed frontmatter, in YAML, without the '---' lines

    Returns:
        dict: {"path", "keys"} : the path of the repaired note and the keys of its frontmatter
    """
    document = vault.repair(path, frontmatter)
    return {"path": vault.relative(document.path), "keys": list(document.metadata)}
