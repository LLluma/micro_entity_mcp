from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from micro_entity import vcs
from micro_entity.codec import CommentedMap
from micro_entity.entity import Entity
from micro_entity.markdown_store import MarkdownStore
from micro_entity.partition import StoreProvider, UnresolvedSegmentError
from micro_entity.query import entity_matches_text
from micro_entity.query import query as query_entities
from micro_entity.store import NotFoundError
from micro_entity.validation import FormError
from servers.schemas import (
    CommitsResult,
    DiffResult,
    HealthResult,
    ItemCommitResult,
    ItemResult,
    ItemsResult,
    ListResult,
)


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    instructions: str
    status_values: set[str]
    normalize: Callable[[CommentedMap], CommentedMap] | None = None
    normalize_id: Callable[[str], str] | None = None
    reserved_keys: frozenset[str] = field(default=frozenset({"created", "updated", "id"}))


def _entity_to_dict(entity: Entity) -> dict:
    """Convert an Entity to a JSON-safe dict (timestamps as ISO strings)."""
    return entity.model_dump(mode="json")


def _resolve_store(
    provider: StoreProvider,
    project: str | None,
) -> MarkdownStore:
    """Resolve the store for a tool call; raise ToolError on failure."""
    try:
        return provider.get(project)
    except UnresolvedSegmentError as e:
        raise ToolError(str(e)) from e


def _require_repo(store: MarkdownStore) -> Path:
    """Resolve the enclosing git repo root for the store's partition dir.

    Raise ``ToolError("storage is not under git")`` if the dir is not under a
    git repository.
    """
    try:
        return vcs.find_repo_root(store.directory)
    except vcs.NotAGitRepoError as e:
        raise ToolError("storage is not under git") from e


def register_common_tools(mcp: FastMCP, provider: StoreProvider, cfg: ProfileConfig) -> None:
    """Register the profile-agnostic tool surface on *mcp*, parameterized by *cfg*."""

    @mcp.tool(annotations={"readOnlyHint": True})
    def health() -> HealthResult:
        """Health check; returns "ok", allowed status values, and partition resolution."""
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
            "status_values": sorted(cfg.status_values),
            "base": str(provider.base),
            "segment": seg,
            "dir": dir_val,
        }

    @mcp.tool(annotations={"readOnlyHint": True})
    def get(id: str, project: str = "") -> ItemResult:
        """Fetch one entity by id."""
        store = _resolve_store(provider, project)
        id = store.normalize_id(id)
        try:
            entity = store.get(id, normalize=cfg.normalize)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        except (FormError, ValueError) as e:
            raise ToolError(str(e)) from e
        return {"item": _entity_to_dict(entity)}

    @mcp.tool(name="list", annotations={"readOnlyHint": True})
    def list_entities(project: str = "", include_body: bool = False) -> ListResult:
        """List all entities in the partition; malformed records are quarantined
        into `errors`.  When ``include_body`` is False (default), the ``body``
        field is omitted from each item."""
        store = _resolve_store(provider, project)
        entities, errors = store.load_all(normalize=cfg.normalize)
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

    @mcp.tool(annotations={"readOnlyHint": True})
    def query(
        criteria: Annotated[
            dict[str, list] | None,
            Field(
                description="{key: [values]}: within-key OR, across-key AND; type-strict matching."
            ),
        ] = None,
        project: str = "",
    ) -> ItemsResult:
        """Return entities whose attributes match `criteria`.

        `criteria` has the shape `{key: [values]}`: each key maps to a list of accepted
        values. Matching is within-key OR, across-key AND — a record matches a key if its
        attribute equals ANY listed value, and must match every key given. Matching is
        type-strict: a stored `1.0` is not matched by `1`, and `bool`/`int` never
        cross-match, so pass correctly-typed values.
        """
        store = _resolve_store(provider, project)
        entities, _ = store.load_all(normalize=cfg.normalize)
        matched = query_entities(entities, criteria or {})
        return {"items": [_entity_to_dict(e) for e in matched]}

    @mcp.tool(annotations={"readOnlyHint": True})
    def search(
        text: str,
        project: str = "",
        include_body: bool = False,
    ) -> ItemsResult:
        """Case-insensitive full-text search over entity body and
        attributes.  When ``include_body`` is False (default), the ``body``
        field is omitted from each item."""
        store = _resolve_store(provider, project)
        entities, _ = store.load_all(normalize=cfg.normalize)
        matched = [e for e in entities if entity_matches_text(e, text)]
        items: list[dict] = []
        for e in matched:
            d = _entity_to_dict(e)
            if not include_body:
                d.pop("body", None)
            items.append(d)
        return {"items": items}

    @mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True})
    def patch_body(
        id: str,
        old: Annotated[
            str, Field(description="Literal text to match in the body; must occur exactly once.")
        ],
        new: Annotated[str, Field(description="Replacement text for the matched occurrence.")],
        project: str = "",
    ) -> ItemCommitResult:
        """Scoped, literal string replacement inside an entity's body.

        Replaces exactly one occurrence of ``old`` with ``new``.
        """
        store = _resolve_store(provider, project)
        id = store.normalize_id(id)
        root = _require_repo(store)
        try:
            entity = store.get(id, normalize=cfg.normalize)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        except (FormError, ValueError) as e:
            raise ToolError(str(e)) from e

        current_body = entity.body or ""
        count = current_body.count(old)
        if count == 0:
            raise ToolError("patch text not found")
        if count > 1:
            raise ToolError("patch text not unique")

        new_body = current_body.replace(old, new, 1)

        try:
            updated = store.update(id, body=new_body, normalize=cfg.normalize)
        except (FormError, ValueError) as e:
            raise ToolError(str(e)) from e
        sha = vcs.commit_paths(root, [store.path_for(id)], f"patch_body {cfg.name} {id}")

        return {"item": _entity_to_dict(updated), "commit": sha}

    @mcp.tool(annotations={"readOnlyHint": True})
    def history(
        id: str,
        project: str = "",
        limit: Annotated[
            int, Field(description="Maximum number of commits to return (newest first).")
        ] = 20,
    ) -> CommitsResult:
        """Return the git commit history for a single entity file."""
        store = _resolve_store(provider, project)
        id = store.normalize_id(id)
        root = _require_repo(store)
        if not vcs.path_in_history(root, store.path_for(id)):
            raise ToolError(f"not found: {id}")
        return {"commits": vcs.file_log(root, store.path_for(id), limit)}

    @mcp.tool(annotations={"readOnlyHint": True})
    def diff(
        id: str,
        ref: Annotated[
            str | None,
            Field(description="Git ref or sha; with no refs, shows the last change to the file."),
        ] = None,
        to: Annotated[
            str | None,
            Field(description="Optional second git ref; diff is ref..to (else ref..working-tree)."),
        ] = None,
        project: str = "",
    ) -> DiffResult:
        """Return the unified diff for an entity file.

        With no refs (the default), shows the last commit that touched this
        file versus its parent (or initial addition for a first commit).
        """
        store = _resolve_store(provider, project)
        id = store.normalize_id(id)
        root = _require_repo(store)
        if not vcs.path_in_history(root, store.path_for(id)):
            raise ToolError(f"not found: {id}")
        if ref is None and to is None:
            return {"diff": vcs.last_change_diff(root, store.path_for(id))}
        effective_ref = ref if ref is not None else "HEAD"
        return {"diff": vcs.file_diff(root, store.path_for(id), effective_ref, to)}

    @mcp.tool(annotations={"destructiveHint": False})
    def revert(
        id: str,
        ref: Annotated[
            str, Field(description="Git ref or sha to restore the entity's content from.")
        ],
        project: str = "",
    ) -> ItemCommitResult:
        """Restore an entity to its contents at *ref* and commit forward.

        History is never rewritten.
        """
        store = _resolve_store(provider, project)
        id = store.normalize_id(id)
        root = _require_repo(store)
        if not vcs.path_in_history(root, store.path_for(id)):
            raise ToolError(f"not found: {id}")
        entity_path = store.path_for(id)
        content = vcs.read_at_ref(root, entity_path, ref)
        store.atomic_write(entity_path, content)
        sha = vcs.commit_paths(root, [entity_path], f"revert {cfg.name} {id} to {ref}")
        return {"item": _entity_to_dict(store.get(id, normalize=cfg.normalize)), "commit": sha}
