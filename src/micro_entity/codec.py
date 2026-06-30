from io import StringIO

from ruamel.yaml import YAML, CommentedMap


class CodecError(ValueError):
    """Raised on malformed codec input."""

    pass


def parse_document(text: str) -> tuple[CommentedMap, str | None]:
    """Parse markdown frontmatter + body into parts.

    Returns (frontmatter_map, body_text) where body_text is None if
    no body region exists or it contains only whitespace.
    Raises CodecError on malformed input.
    """
    stripped = text.strip()
    if not stripped:
        raise CodecError("Missing opening ---")

    # Opening --- must be on the first non-empty line
    lines = text.splitlines(keepends=True)
    first_line = lines[0].rstrip("\r\n")
    if first_line != "---":
        raise CodecError("Missing opening --- delimiter")

    # Find closing --- after the opening
    closing_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            closing_idx = i
            break

    if closing_idx is None:
        raise CodecError("Missing closing --- delimiter for frontmatter block")

    yaml_text = "".join(lines[1:closing_idx])

    # Parse frontmatter
    yaml = YAML()
    yaml.preserve_quotes = True
    stream = StringIO(yaml_text)
    fm = yaml.load(stream)

    if fm is None:
        fm = CommentedMap()
    elif not isinstance(fm, CommentedMap):
        raise CodecError(f"Frontmatter must be a YAML mapping, got {type(fm).__name__}")

    # Extract body
    body_lines = lines[closing_idx + 1 :]
    body = "".join(body_lines)
    if body.strip() == "":
        body = None

    return fm, body
