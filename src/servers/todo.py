"""Todo profile server — exposes todo management via FastMCP."""

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from micro_entity import vcs
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


def _require_repo(store: MarkdownStore) -> Path:
    """Resolve the enclosing git repo root for the store's partition dir.

    Raise ``ToolError("storage is not under git")`` if the dir is not under a
    git repository.
    """
    try:
        return vcs.find_repo_root(store.directory)
    except vcs.NotAGitRepoError as e:
        raise ToolError("storage is not under git") from e


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
        """Health check; returns "ok" and the allowed status values
        (todo, in-progress, done, blocked)."""
        seg = provider.default_segment
        if seg:
            try:
                store = provider.get(None)
                dir_val = str(store.directory)
            except UnresolvedSegmentError:
                dir_val = None
        else:
            dir_val = None
        return {
            "status": "ok",
            "status_values": sorted(STATUS_VALUES),
            "base": str(provider.base),
            "segment": seg,
            "dir": dir_val,
        }

    @mcp.tool
    def create(
        body: str,
        attributes: dict | None = None,
        project: str = "",
    ) -> dict:
        """Create a todo with the given body; auto-assigns id and order
        and defaults status to "todo".  `attributes` adds extra fields
        (reserved keys id/created/updated are rejected); `project` selects
        the per-project partition (defaults to the workspace)."""
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
        root = _require_repo(store)
        created = store.create(new_id, attributes=attrs, body=body)
        vcs.commit_paths(root, [store.path_for(new_id)], f"create todo {new_id}")
        return {"item": _entity_to_dict(created)}

    @mcp.tool
    def get(id: str, project: str = "") -> dict:
        """Fetch one todo entity by id."""
        store = _resolve_store(provider, project)
        try:
            entity = store.get(id)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        return {"item": _entity_to_dict(entity)}

    @mcp.tool(name="list")
    def list_items(project: str = "", include_body: bool = False) -> dict:
        """List all todos in the partition, plus any load errors.

        When ``include_body`` is False (default), the ``body`` key is stripped
        from each item dict. When True, the full entity dict including ``body``
        is returned.
        """
        store = _resolve_store(provider, project)
        entities, errors = store.load_all()
        items: list[dict] = []
        for e in entities:
            d = _entity_to_dict(e)
            if not include_body:
                d.pop("body", None)
            items.append(d)
        return {
            "items": items,
            "errors": [{"id": err.id, "reason": err.reason} for err in errors],
        }

    @mcp.tool
    def query(
        criteria: dict[str, list] | None = None,
        project: str = "",
    ) -> dict:
        """Return todos whose attributes match `criteria`.

        `criteria` has the shape `{key: [values]}`: each key maps to a list of accepted
        values. Matching is within-key OR, across-key AND — a record matches a key if its
        attribute equals ANY listed value, and must match every key given. Matching is
        type-strict: a stored `1.0` is not matched by `1`, and `bool`/`int` never
        cross-match, so pass correctly-typed values.
        """
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
        attributes: dict | None = None,
        project: str = "",
    ) -> dict:
        """Update a todo's status, order, body, or arbitrary custom attributes by id;
        other fields are preserved.

        The ``attributes`` bag lets callers set any non-reserved keys (id, created,
        updated are rejected). Explicit params (status, order) override the same
        keys in ``attributes``.
        """
        store = _resolve_store(provider, project)
        # Build from a copy of the provided attributes bag
        patch: dict = dict(attributes) if attributes else {}
        # Reject reserved keys
        bad = RESERVED_KEYS & patch.keys()
        if bad:
            raise ToolError(f"cannot set reserved keys: {sorted(bad)}")
        # Explicit params override the bag
        if status is not None:
            patch[STATUS_KEY] = status
        if order is not None:
            patch[ORDER_KEY] = order
        # Validate the effective status (whether from bag or explicit)
        if STATUS_KEY in patch:
            try:
                validate_against_set(patch[STATUS_KEY], STATUS_VALUES)
            except FormError as e:
                raise ToolError(str(e)) from e
        body_arg = body if body is not None else UNSET
        root = _require_repo(store)
        try:
            updated = store.update(
                id,
                attributes=patch or None,
                body=body_arg,
            )
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        vcs.commit_paths(root, [store.path_for(id)], f"update todo {id}")
        return {"item": _entity_to_dict(updated)}

    @mcp.tool
    def commit(ids: list[str], message: str, project: str = "") -> dict:
        """Stage and commit the named todo files.

        Returns the new commit SHA or ``None`` when there were no pending
        changes.  Raises ``ToolError("storage is not under git")`` if the
        store's partition directory is not inside a git repository.
        """
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        paths = [store.path_for(i) for i in ids]
        sha = vcs.commit_paths(root, paths, message)
        return {"ok": True, "commit": sha, "ids": ids}

    @mcp.tool
    def patch_body(
        id: str,
        old: str,
        new: str,
        project: str = "",
    ) -> dict:
        """Replace a single literal occurrence of *old* with *new* inside the
        entity's body.  Raises ``ToolError`` when the text is not found,
        occurs more than once, or the entity id does not exist."""
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        try:
            current = store.get(id)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e

        body = current.body or ""
        count = body.count(old)
        if count == 0:
            raise ToolError("patch text not found")
        if count > 1:
            raise ToolError("patch text not unique")

        new_body = body.replace(old, new, 1)
        updated = store.update(id, body=new_body)
        vcs.commit_paths(root, [store.path_for(id)], f"patch_body todo {id}")
        return {"item": _entity_to_dict(updated)}

    @mcp.tool
    def delete(id: str, project: str = "") -> dict:
        """Delete a todo entity by id."""
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        try:
            store.delete(id)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        vcs.commit_paths(root, [store.path_for(id)], f"delete todo {id}")
        return {"ok": True, "id": id}

    @mcp.tool
    def diff(
        id: str,
        ref: str = "HEAD",
        to: str | None = None,
        project: str = "",
    ) -> dict:
        """Return the unified diff for a todo file between *ref* and *to*.

        When *to* is ``None`` the diff is between *ref* and the working tree.
        Returns ``{"diff": <text>}`` -- an empty string when there is no
        difference.
        """
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        return {"diff": vcs.file_diff(root, store.path_for(id), ref, to)}

    @mcp.tool(name="next")
    def next_tool(project: str = "") -> dict:
        """Return the first actionable todo (status todo or in-progress,
        lowest order), or null if none."""
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

    @mcp.tool
    def clear(project: str = "") -> dict:
        """Delete all todos in the partition."""
        store = _resolve_store(provider, project)
        n = store.clear()
        return {"ok": True, "cleared": n}

    @mcp.tool
    def history(
        id: str,
        project: str = "",
        limit: int = 20,
    ) -> dict:
        """Return the git commit history for a single todo file.

        Returns ``{"commits": [...]}`` where each entry is ``{"sha", "date",
        "message"}`` ordered newest-first.  ``limit`` caps the number of
        records returned (default 20).  Raises ``ToolError`` if the store is
        not under git.
        """
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        return {"commits": vcs.file_log(root, store.path_for(id), limit)}

    @mcp.tool
    def is_complete(project: str = "") -> dict:
        """True when no todo is still open (todo/in-progress/blocked)."""
        store = _resolve_store(provider, project)
        entities, _ = store.load_all()
        return {
            "complete": not any(
                e.attributes.get(STATUS_KEY) in {"todo", "in-progress", "blocked"} for e in entities
            )
        }

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
