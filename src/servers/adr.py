"""ADR (Architecture Decision Record) server — exposes ADR management via FastMCP."""

import os
from datetime import UTC, datetime
from datetime import date as date_cls
from pathlib import Path

from fastmcp import FastMCP

from micro_entity.entity import Entity
from micro_entity.markdown_store import MarkdownStore

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

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

ADR_DIR = os.environ.get("ADR_DIR", str(Path.home() / ".micro_entity_adr"))
mcp = build_server(MarkdownStore(Path(ADR_DIR)))

if __name__ == "__main__":
    mcp.run()
