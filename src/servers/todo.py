"""Todo profile server — exposes todo management via FastMCP."""

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from micro_entity.entity import Entity
from micro_entity.markdown_store import MarkdownStore
from micro_entity.validation import FormError, validate_against_set

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


def _next_order(store: MarkdownStore) -> int:
    """Return max existing integer `order` attribute + 1, or 1 if none."""
    entities, _ = store.load_all()
    found: list[int] = []
    for entity in entities:
        val = entity.attributes.get("order")
        if isinstance(val, int) and not isinstance(val, bool):
            found.append(val)
    return max(found) + 1 if found else 1


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

    @mcp.tool
    def create(body: str, attributes: dict | None = None) -> dict:
        attrs = dict(attributes) if attributes else {}
        status = attrs.get(STATUS_KEY, DEFAULT_STATUS)
        try:
            validate_against_set(status, STATUS_VALUES)
        except FormError as e:
            raise ToolError(str(e)) from e
        attrs[STATUS_KEY] = status
        attrs[ORDER_KEY] = _next_order(store)
        new_id = _next_id(store)
        created = store.create(new_id, attributes=attrs, body=body)
        return _entity_to_dict(created)

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

TODO_DIR = os.environ.get("TODO_DIR", str(Path.home() / ".micro_entity_todo"))
mcp = build_server(MarkdownStore(Path(TODO_DIR)))

if __name__ == "__main__":
    mcp.run()
