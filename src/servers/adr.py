"""ADR (Architecture Decision Record) server — exposes ADR management via FastMCP."""

import os
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
