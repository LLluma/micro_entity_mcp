"""Todo profile server — exposes todo management via FastMCP."""

import os
from pathlib import Path

from fastmcp import FastMCP

from micro_entity.entity import Entity
from micro_entity.markdown_store import MarkdownStore

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

STATUS_VALUES: set[str] = {"todo", "in-progress", "done", "blocked"}
STATUS_KEY: str = "status"
ORDER_KEY: str = "order"
DEFAULT_STATUS: str = "todo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity_to_dict(entity: Entity) -> dict:
    """Convert an Entity to a JSON-safe dict (timestamps as ISO strings)."""
    return entity.model_dump(mode="json")


def _next_id(store: MarkdownStore) -> str:
    """Return the next sequential ID based on existing entity filenames.

    Only entity ids that are purely integer strings (e.g. ``"0001"``, ``"42"``)
    are considered. Non-integer stems are skipped when determining the next
    sequential id.

    Returns ``max + 1`` formatted as ``"{:04d}"`` — zero-padded to width 4;
    widths grow naturally beyond 4 when needed.
    """
    entities, _ = store.load_all()
    max_n: int = 0
    for entity in entities:
        stem = entity.id
        if stem.isdigit() and len(stem) > 0:
            val = int(stem)
            if val >= max_n:
                max_n = val
    return format(max_n + 1, "04d")


# ---------------------------------------------------------------------------
# Factory — the testability seam
# ---------------------------------------------------------------------------


def build_server(store: MarkdownStore) -> FastMCP:
    """Build the FastMCP server for the todo profile.

    All tools are registered inside this function so tests can inject a
    mock / temporary store.
    """
    mcp = FastMCP("todo")

    @mcp.tool
    def health() -> dict:
        return {"status": "ok", "status_values": sorted(STATUS_VALUES)}

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

TODO_DIR = os.environ.get("TODO_DIR", str(Path.home() / ".micro_entity_todo"))
mcp = build_server(MarkdownStore(Path(TODO_DIR)))

if __name__ == "__main__":
    mcp.run()
