"""ADR (Architecture Decision Record) server — exposes ADR management via FastMCP."""

import os
from datetime import UTC, datetime
from datetime import date as date_cls
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from micro_entity.codec import entity_from_parts, parse_document
from micro_entity.entity import Entity
from micro_entity.markdown_store import MarkdownStore
from micro_entity.store import NotFoundError
from micro_entity.validation import FormError, validate_against_set

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

STATUS_VALUES: set[str] = {"Proposed", "Accepted", "Superseded"}
STATUS_KEY: str = "status"
SUPERSEDES_KEY: str = "supersedes"
SUPERSEDED_BY_KEY: str = "superseded_by"
DEFAULT_STATUS: str = "Proposed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_frontmatter(fm: dict) -> dict:
    """Derive created/updated timestamps from a legacy ``date`` field.

    If ``created`` and ``updated`` already exist, return *fm* unchanged.
    Otherwise derive a midnight-UTC datetime from ``date`` (the structurally
    parsed YAML value — may be ``datetime``, ``date``, or ``str``).
    Mutates *fm* in place and returns it.
    """
    got_created: bool = "created" in fm
    got_updated: bool = "updated" in fm

    if got_created and got_updated:
        return fm

    raw_date = fm.get("date")
    if raw_date is None:
        return fm

    # datetime is subclass of date — merged isinstance catches both
    if isinstance(raw_date, (datetime, date_cls)):
        ts = datetime(raw_date.year, raw_date.month, raw_date.day, tzinfo=UTC)
    elif isinstance(raw_date, str):
        parsed = date_cls.fromisoformat(raw_date[:10])
        ts = datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)
    else:
        return fm

    if not got_created:
        fm["created"] = ts
    if not got_updated:
        fm["updated"] = ts

    return fm


def _get_migrated(store: MarkdownStore, id: str) -> Entity:
    """Read one record, migrating legacy timestamps, and return the Entity.

    Raises ``NotFoundError`` if the file does not exist.
    """
    path = store._path_for(id)
    if not path.is_file():
        raise NotFoundError(f"decision not found: {id}")
    fm, body = parse_document(path.read_text(encoding="utf-8"))
    fm = _normalize_frontmatter(fm)

    # Drop the legacy ``date`` key so it doesn't pollute entity attributes
    fm.pop("date", None)

    return entity_from_parts(id, fm, body)


def _entity_to_dict(entity: Entity) -> dict:
    """Convert an Entity to a JSON-safe dict (timestamps as ISO strings)."""
    return entity.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Factory — the testability seam
# ---------------------------------------------------------------------------


def build_server(store: MarkdownStore) -> FastMCP:
    """Build the FastMCP server for the ADR profile.

    All tools are registered inside this function so tests can inject a
    mock / temporary store.
    """
    mcp = FastMCP("adr")

    @mcp.tool
    def health() -> dict:
        return {"status": "ok", "status_values": sorted(STATUS_VALUES)}

    @mcp.tool
    def add(
        id: str,
        title: str,
        body: str,
        attributes: dict | None = None,
    ) -> dict:
        attrs = dict(attributes) if attributes else {}
        attrs["title"] = title

        status = attrs.get(STATUS_KEY, DEFAULT_STATUS)
        try:
            validate_against_set(status, STATUS_VALUES)
        except FormError as e:
            raise ToolError(str(e)) from e
        attrs[STATUS_KEY] = status

        try:
            entity = store.create(id, attributes=attrs, body=body)
        except FileExistsError:
            raise ToolError(f"decision already exists: {id}") from None
        except FormError as e:
            raise ToolError(str(e)) from e

        return _entity_to_dict(entity)

    @mcp.tool
    def get(id: str) -> dict:
        try:
            entity = _get_migrated(store, id)
        except NotFoundError as e:
            raise ToolError(str(e)) from None
        except FormError as e:
            raise ToolError(str(e)) from e

        return _entity_to_dict(entity)

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

ADR_DIR = os.environ.get("ADR_DIR", str(Path.home() / ".micro_entity_adr"))
mcp = build_server(MarkdownStore(Path(ADR_DIR)))

if __name__ == "__main__":
    mcp.run()
