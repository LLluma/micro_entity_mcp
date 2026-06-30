# pyright: reportArgumentType=false
from collections.abc import Mapping
from datetime import datetime
from io import StringIO

from ruamel.yaml import YAML, CommentedMap

from micro_entity.entity import Entity


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


def entity_from_parts(
    id: str,
    frontmatter: Mapping[str, object],
    body: str | None,
) -> Entity:
    """Build Entity from parsed frontmatter + body + supplied id.

    Reads 'created' and 'updated' as timestamps (ISO-8601 strings or datetimes).
    All other frontmatter keys become attributes.
    Raises CodecError if timestamps missing/unparseable.
    Propagates Entity validation errors unchanged.
    """
    timestamps: dict[str, datetime] = {}
    for field in ("created", "updated"):
        raw_obj = frontmatter.get(field)
        if raw_obj is None:
            raise CodecError(f"missing required timestamp: {field}")
        if isinstance(raw_obj, datetime):
            timestamps[field] = raw_obj
        elif isinstance(raw_obj, str):
            try:
                timestamps[field] = datetime.fromisoformat(raw_obj)
            except (TypeError, ValueError) as exc:
                raise CodecError(f"unparseable timestamp for {field}: {raw_obj!r}") from exc
        else:
            raise CodecError(f"unparseable timestamp for {field}: {raw_obj!r}")

    attributes: dict[str, object] = {k: v for k, v in frontmatter.items() if k not in timestamps}
    return Entity(
        id=id,
        created=timestamps["created"],
        updated=timestamps["updated"],
        body=body,
        attributes=attributes,
    )


def serialize_document(frontmatter: CommentedMap, body: str | None) -> str:
    """Render frontmatter + body back into markdown document text.

    Preserves key order and comments in frontmatter (round-trip stable).
    body=None → no body region; body="" → empty body region; body="..." → body content.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    stream = StringIO()
    yaml.dump(frontmatter, stream)
    yaml_content = stream.getvalue()

    # Ensure each line ends with a newline; remove trailing newline so we
    # can control the delimiter separator atomically below.
    yaml_lines = yaml_content.rstrip("\n")

    if body is None:
        # Frontmatter only — no body region at all
        return f"---\n{yaml_lines}\n---"
    else:
        # body is "" → ending "---\n" then body (empty)
        # body is "..." → ending "---\n" then body verbatim
        return f"---\n{yaml_lines}\n---\n{body}"
