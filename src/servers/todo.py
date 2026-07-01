"""Todo profile server — exposes todo management via FastMCP."""

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from micro_entity.entity import Entity
from micro_entity.markdown_store import UNSET, MarkdownStore
from micro_entity.partition import (
    StoreProvider,
    UnresolvedSegmentError,
    resolve_segment,
)
from micro_entity.query import query as query_entities
from micro_entity.store import NotFoundError
from micro_entity.validation import FormError, validate_against_set

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

STATUS_VALUES: set[str] = {"todo", "in-progress", "done", "blocked"}
STATUS_KEY: str = "status"
ORDER_KEY: str = "order"
DEFAULT_STATUS: str = "todo"
RESERVED_KEYS: frozenset[str] = frozenset({"created", "updated", "id"})


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


def _resolve_store(
    provider: StoreProvider,
    project: str | None,
) -> MarkdownStore:
    """Resolve the store for a tool call; raise ToolError on failure."""
    try:
        return provider.get(project)
    except UnresolvedSegmentError as e:
        raise ToolError(str(e)) from e


def build_server(provider: StoreProvider) -> FastMCP:
    """Build the FastMCP server for the todo profile.

    All tools are registered inside this function so tests can inject a
    mock / temporary store.
    """
    mcp = FastMCP("todo")

    @mcp.tool
    def health() -> dict:
        return {"status": "ok", "status_values": sorted(STATUS_VALUES)}

    @mcp.tool
    def create(
        body: str,
        attributes: dict | None = None,
        project: str | None = None,
    ) -> dict:
        store = _resolve_store(provider, project)
        attrs = dict(attributes) if attributes else {}
        bad = RESERVED_KEYS & attrs.keys()
        if bad:
            raise ToolError(f"cannot set reserved keys: {sorted(bad)}")
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

    @mcp.tool
    def get(id: str, project: str | None = None) -> dict:
        store = _resolve_store(provider, project)
        try:
            entity = store.get(id)
        except NotFoundError as e:
            raise ToolError(str(e)) from e
        return _entity_to_dict(entity)

    @mcp.tool(name="list")
    def list_items(project: str | None = None) -> dict:
        store = _resolve_store(provider, project)
        entities, errors = store.load_all()
        return {
            "items": [_entity_to_dict(e) for e in entities],
            "errors": [{"id": err.id, "reason": err.reason} for err in errors],
        }

    @mcp.tool
    def query(
        criteria: dict[str, list] | None = None,
        project: str | None = None,
    ) -> dict:
        store = _resolve_store(provider, project)
        entities, _ = store.load_all()
        matched = query_entities(entities, criteria or {})
        return {"items": [_entity_to_dict(e) for e in matched]}

    @mcp.tool
    def update(
        id: str,
        status: str | None = None,
        order: int | None = None,
        body: str | None = None,
        project: str | None = None,
    ) -> dict:
        store = _resolve_store(provider, project)
        attributes: dict = {}
        if status is not None:
            try:
                validate_against_set(status, STATUS_VALUES)
            except FormError as e:
                raise ToolError(str(e)) from e
            attributes[STATUS_KEY] = status
        if order is not None:
            attributes[ORDER_KEY] = order
        body_arg = body if body is not None else UNSET
        try:
            updated = store.update(
                id,
                attributes=attributes or None,
                body=body_arg,
            )
        except NotFoundError as e:
            raise ToolError(str(e)) from e
        return _entity_to_dict(updated)

    @mcp.tool
    def delete(id: str, project: str | None = None) -> dict:
        store = _resolve_store(provider, project)
        try:
            store.delete(id)
        except NotFoundError as e:
            raise ToolError(str(e)) from e
        return {"deleted": id}

    @mcp.tool(name="next")
    def next_tool(project: str | None = None) -> dict | None:
        store = _resolve_store(provider, project)
        entities, _ = store.load_all()
        actionable = [
            e for e in entities if e.attributes.get(STATUS_KEY) in {"todo", "in-progress"}
        ]
        if not actionable:
            return None

        def _sort_key(e: Entity):
            val = e.attributes.get(ORDER_KEY)
            if isinstance(val, int) and not isinstance(val, bool):
                return (0, val)
            else:
                return (1, 0)

        actionable.sort(key=_sort_key)
        return _entity_to_dict(actionable[0])

    @mcp.tool
    def clear(project: str | None = None) -> dict:
        store = _resolve_store(provider, project)
        store.clear()
        return {"cleared": True}

    @mcp.tool
    def is_complete(project: str | None = None) -> bool:
        store = _resolve_store(provider, project)
        entities, _ = store.load_all()
        return not any(
            e.attributes.get(STATUS_KEY) in {"todo", "in-progress", "blocked"} for e in entities
        )

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

TODO_DIR = os.environ.get("TODO_DIR", str(Path.home() / ".micro_entity_todo"))
_provider = StoreProvider(
    Path(TODO_DIR),
    resolve_segment(explicit=None, workspace=os.getcwd()),
)
mcp = build_server(_provider)

if __name__ == "__main__":
    mcp.run()
