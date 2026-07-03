"""Todo profile server — exposes todo management via FastMCP."""

import os
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from micro_entity import vcs
from micro_entity.entity import Entity
from micro_entity.markdown_store import MarkdownStore
from micro_entity.partition import (
    StoreProvider,
    resolve_segment,
)
from micro_entity.store import NotFoundError
from micro_entity.validation import FormError, validate_against_set
from servers._common import (
    ProfileConfig,
    _entity_to_dict,
    _require_repo,
    _resolve_store,
    register_common_tools,
)
from servers.schemas import (
    CompleteResult,
    ItemCommitResult,
    ItemResult,
    OkIdCommitResult,
)

# ---------------------------------------------------------------------------
# Cross-cutting server instructions
# ---------------------------------------------------------------------------

TODO_INSTRUCTIONS = """\
Todo profile: ephemeral run-state entities. Ids are machine-assigned sequential
zero-padded numbers; statuses are todo / in-progress / done / blocked.

Every tool returns a JSON object. Conventions:
- single entity -> {"item": {...}} (or {"item": null} when absent)
- collection -> {"items": [...], "errors": [...]}
- mutation -> {"ok": true, ...}
- any tool that creates a commit adds "commit": "<sha>" (null on a no-op)

Storage is git-backed: the partition directory must be inside a git repository,
otherwise any store operation fails with "storage is not under git".

The `project` argument selects the per-project partition (defaults to the
workspace); `health` reports the resolved base / segment / dir.

A read issued in the same parallel batch as a write may not observe that write;
sequence dependent calls rather than batching a read with its write.

A missing id fails with "not found: {id}".
"""
STATUS_VALUES: set[str] = {"todo", "in-progress", "done", "blocked"}
STATUS_KEY: str = "status"
ORDER_KEY: str = "order"
DEFAULT_STATUS: str = "todo"
RESERVED_KEYS: frozenset[str] = frozenset({"created", "updated", "id"})


# ---------------------------------------------------------------------------
# Helpers (todo-specific)
# ---------------------------------------------------------------------------


def _normalize_todo_id(raw: str) -> str:
    """Return *raw* zero-padded to width 4 when digit-only, else unchanged.

    Idempotent: ``_normalize_todo_id(_normalize_todo_id(x)) == _normalize_todo_id(x)``.
    """
    if raw.isdigit():
        return f"{int(raw):04d}"
    return raw


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


def _todo_progress(store: MarkdownStore) -> dict:
    """Return {done, total} for the current partition state."""
    entities, _ = store.load_all()
    total = len(entities)
    done = sum(1 for e in entities if e.attributes.get(STATUS_KEY) == "done")
    return {"done": done, "total": total}


def build_server(provider: StoreProvider) -> FastMCP:
    """Build the FastMCP server for the todo profile.

    Common tools come from the shared scaffold; only ``create``, ``next``,
    ``is_complete`` and ``delete`` are todo-specific.
    """
    cfg = ProfileConfig(
        name="todo",
        instructions=TODO_INSTRUCTIONS,
        status_values=STATUS_VALUES,
        normalize=None,
        normalize_id=_normalize_todo_id,
        reserved_keys=RESERVED_KEYS,
        progress=_todo_progress,
    )
    mcp = FastMCP("todo", instructions=TODO_INSTRUCTIONS)
    register_common_tools(mcp, provider, cfg)

    @mcp.tool(annotations={"destructiveHint": False})
    def create(
        body: str,
        attributes: Annotated[
            dict | None,
            Field(
                description="Free-form attribute bag; "
                "reserved keys id/created/updated are rejected."
            ),
        ] = None,
        status: str | None = None,
        project: str = "",
    ) -> ItemCommitResult:
        """Create a todo with the given body; auto-assigns id and order,
        defaults status to "todo"."""
        store = _resolve_store(provider, project)
        attrs = dict(attributes) if attributes else {}
        bad = RESERVED_KEYS & attrs.keys()
        if bad:
            raise ToolError(f"cannot set reserved keys: {sorted(bad)}")
        if status is not None:
            attrs[STATUS_KEY] = status
        status = attrs.get(STATUS_KEY) or DEFAULT_STATUS
        try:
            validate_against_set(status, STATUS_VALUES)
        except FormError as e:
            raise ToolError(str(e)) from e
        attrs[STATUS_KEY] = status
        attrs[ORDER_KEY] = _next_order(store)
        new_id = _next_id(store)
        root = _require_repo(store)
        created = store.create(new_id, attributes=attrs, body=body)
        sha = vcs.commit_paths(root, [store.path_for(new_id)], f"create todo {new_id}")
        result: dict = {"item": _entity_to_dict(created), "commit": sha}
        result["progress"] = _todo_progress(store)
        return result  # type: ignore[return-value]

    @mcp.tool(name="next", annotations={"readOnlyHint": True})
    def next_tool(project: str = "") -> ItemResult:
        """Return the first actionable todo (status todo or in-progress,
        lowest order) as {"item": <entity>}, or {"item": null} if none."""
        store = _resolve_store(provider, project)
        entities, _ = store.load_all()
        actionable = [
            e for e in entities if e.attributes.get(STATUS_KEY) in {"todo", "in-progress"}
        ]
        if not actionable:
            return {"item": None}

        def _sort_key(e: Entity):
            val = e.attributes.get(ORDER_KEY)
            if isinstance(val, int) and not isinstance(val, bool):
                return (0, val)
            else:
                return (1, 0)

        actionable.sort(key=_sort_key)
        return {"item": _entity_to_dict(actionable[0])}

    @mcp.tool(annotations={"readOnlyHint": True})
    def is_complete(project: str = "") -> CompleteResult:
        """True when no todo is still open (todo/in-progress/blocked)."""
        store = _resolve_store(provider, project)
        entities, _ = store.load_all()
        return {
            "complete": not any(
                e.attributes.get(STATUS_KEY) in {"todo", "in-progress", "blocked"} for e in entities
            )
        }

    @mcp.tool(annotations={"destructiveHint": True, "idempotentHint": True})
    def delete(id: str, project: str = "") -> OkIdCommitResult:
        """Delete a todo entity by id."""
        store = _resolve_store(provider, project)
        id = store.normalize_id(id)
        root = _require_repo(store)
        try:
            store.delete(id)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        sha = vcs.commit_paths(root, [store.path_for(id)], f"delete todo {id}")
        result: dict = {"ok": True, "id": id, "commit": sha}
        result["progress"] = _todo_progress(store)
        return result  # type: ignore[return-value]

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

TODO_DIR = os.environ.get("TODO_DIR", str(Path.home() / ".micro_entity_todo"))
_provider = StoreProvider(
    Path(TODO_DIR),
    resolve_segment(explicit=None, workspace=os.getcwd()),
    normalize_id=_normalize_todo_id,
)
mcp = build_server(_provider)

if __name__ == "__main__":
    mcp.run()
