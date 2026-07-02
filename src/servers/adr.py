"""ADR (Architecture Decision Record) server — exposes ADR management via FastMCP."""

import os
import re
from datetime import UTC, datetime
from datetime import date as date_cls
from pathlib import Path
from typing import Annotated, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from micro_entity import vcs
from micro_entity.codec import CommentedMap
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
from servers.schemas import (
    CommitResult,
    CommitsResult,
    DiffResult,
    HealthResult,
    ItemCommitResult,
    ItemResult,
    ItemsResult,
    ListResult,
    SupersedeResult,
)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

ADR_INSTRUCTIONS = """\
ADR profile: durable architecture-decision records. Ids are server-assigned,
sequential and zero-padded (ADR-NNNN); statuses are Proposed / Accepted /
Superseded. The log is append-only: there is no delete or clear — a
changed decision is a new record plus a Superseded status on the old one, via
supersede.

Every tool returns a JSON object. Conventions:
- single entity -> {"item": {...}}
- collection -> {"items": [...], "errors": [...]}
- any tool that creates a commit adds "commit": "<sha>" (null on a no-op)

Storage is git-backed: the partition directory must be inside a git repository,
otherwise any store operation fails with "storage is not under git".

The `project` argument selects the per-project partition (defaults to the
workspace); `health` reports the resolved base / segment / dir.

A missing id fails with "not found: {id}".
"""

STATUS_VALUES: set[str] = {"Proposed", "Accepted", "Superseded"}
STATUS_KEY: str = "status"
SUPERSEDES_KEY: str = "supersedes"
SUPERSEDED_BY_KEY: str = "superseded_by"
DEFAULT_STATUS: str = "Proposed"
RESERVED_KEYS: frozenset[str] = frozenset({"created", "updated", "id"})


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
        try:
            parsed = date_cls.fromisoformat(raw_date[:10])
        except ValueError:
            return fm
        ts = datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)
    else:
        return fm

    if not got_created:
        fm["created"] = ts
    if not got_updated:
        fm["updated"] = ts

    return fm


def _adr_normalize(fm: CommentedMap) -> CommentedMap:
    """ADR-profile frontmatter migration passed into the store's normalize hook."""
    fm = cast(CommentedMap, _normalize_frontmatter(fm))
    fm.pop("date", None)
    return fm


def _entity_to_dict(entity: Entity) -> dict:
    """Convert an Entity to a JSON-safe dict (timestamps as ISO strings)."""
    return entity.model_dump(mode="json")


def _entity_matches_text(entity: Entity, needle: str) -> bool:
    """True if ``needle`` (case-insensitive) is a substring of the body or any
    attribute value (stringified)."""
    low = needle.lower()
    # body
    if entity.body is not None and low in entity.body.lower():
        return True
    # attributes
    for value in entity.attributes.values():
        if isinstance(value, list):
            for v in value:
                if low in str(v).lower():
                    return True
        else:
            if low in str(value).lower():
                return True
    return False


_adr_id_re = re.compile(r"^[Aa][Dd][Rr]-?(\d+)$")


def _normalize_adr_id(raw: str) -> str:
    """Canonicalize *raw* to ``ADR-NNNN`` form.

    All-digits strings are treated as bare ordinal (``"7"`` -> ``"ADR-0007"``).
    Cases of ``ADR``, ``adr``, ``ADr``, optionally followed by ``-``, then
    digits are all normalised.  Anything else is returned unchanged.

    Idempotent: ``_normalize_adr_id(_normalize_adr_id(s)) == _normalize_adr_id(s)``.
    """
    if raw.isdigit():
        return f"ADR-{int(raw):04d}"
    m = _adr_id_re.match(raw)
    if m:
        return f"ADR-{int(m.group(1)):04d}"
    return raw


_next_adr_re = re.compile(r"^ADR-(\d+)$")


def _next_adr_id(store: MarkdownStore) -> str:
    """Return the next ADR id based on existing records."""
    entities, _ = store.load_all(normalize=_adr_normalize)
    max_n = 0
    for e in entities:
        m = _next_adr_re.match(e.id)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"ADR-{max_n + 1:04d}"


# ---------------------------------------------------------------------------
# Store resolution helper (mirrors todo.py)
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


def build_server(provider: StoreProvider) -> FastMCP:
    """Build the FastMCP server for the ADR profile.

    All tools are registered inside this function so tests can inject a
    mock / temporary store.
    """
    mcp = FastMCP("adr", instructions=ADR_INSTRUCTIONS)

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
            "status_values": sorted(STATUS_VALUES),
            "base": str(provider.base),
            "segment": seg,
            "dir": dir_val,
        }

    @mcp.tool(annotations={"destructiveHint": False})
    def create(
        title: str,
        body: str,
        attributes: Annotated[
            dict | None,
            Field(
                description="Free-form frontmatter bag; "
                "reserved keys id/created/updated are rejected."
            ),
        ] = None,
        project: str = "",
    ) -> ItemCommitResult:
        """Create an ADR. The server assigns a sequential id (ADR-NNNN);
        default status is "Proposed"."""
        store = _resolve_store(provider, project)
        new_id = _next_adr_id(store)
        attrs = dict(attributes) if attributes else {}
        bad = RESERVED_KEYS & attrs.keys()
        if bad:
            raise ToolError(f"cannot set reserved keys: {sorted(bad)}")
        attrs["title"] = title

        status = attrs.get(STATUS_KEY, DEFAULT_STATUS)
        try:
            validate_against_set(status, STATUS_VALUES)
        except FormError as e:
            raise ToolError(str(e)) from e
        attrs[STATUS_KEY] = status

        root = _require_repo(store)
        try:
            entity = store.create(new_id, attributes=attrs, body=body)
        except FormError as e:
            raise ToolError(str(e)) from e
        sha = vcs.commit_paths(root, [store.path_for(new_id)], f"create adr {new_id}")

        return {"item": _entity_to_dict(entity), "commit": sha}

    @mcp.tool(annotations={"readOnlyHint": True})
    def get(id: str, project: str = "") -> ItemResult:
        """Fetch one ADR by id, migrating legacy date-only records."""
        store = _resolve_store(provider, project)
        try:
            entity = store.get(id, normalize=_adr_normalize)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        except (FormError, ValueError) as e:
            raise ToolError(str(e)) from e

        return {"item": _entity_to_dict(entity)}

    @mcp.tool(name="list", annotations={"readOnlyHint": True})
    def list_decisions(project: str = "", include_body: bool = False) -> ListResult:
        """List all ADRs in the partition; malformed records are quarantined
        into `errors`.  When ``include_body`` is False (default), the ``body``
        field is omitted from each item."""
        store = _resolve_store(provider, project)
        entities, errors = store.load_all(normalize=_adr_normalize)
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

    @mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True})
    def update(
        id: str,
        status: str | None = None,
        body: str | None = None,
        attributes: Annotated[
            dict | None,
            Field(
                description="Free-form frontmatter bag; "
                "reserved keys id/created/updated are rejected."
            ),
        ] = None,
        project: str = "",
    ) -> ItemCommitResult:
        """Update an ADR's status, body, and/or attributes by id."""
        store = _resolve_store(provider, project)
        patch: dict = dict(attributes) if attributes else {}
        bad = RESERVED_KEYS & patch.keys()
        if bad:
            raise ToolError(f"cannot set reserved keys: {sorted(bad)}")
        if status is not None:
            try:
                validate_against_set(status, STATUS_VALUES)
            except FormError as e:
                raise ToolError(str(e)) from e
            patch[STATUS_KEY] = status

        body_arg = body if body is not None else UNSET
        root = _require_repo(store)

        try:
            updated = store.update(
                id,
                attributes=(patch or None),
                body=body_arg,
                normalize=_adr_normalize,
            )
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        except (FormError, ValueError) as e:
            raise ToolError(str(e)) from e
        sha = vcs.commit_paths(root, [store.path_for(id)], f"update adr {id}")

        return {"item": _entity_to_dict(updated), "commit": sha}

    @mcp.tool(annotations={"destructiveHint": True})
    def supersede(old_id: str, new_id: str, project: str = "") -> SupersedeResult:
        """Mark old_id Superseded (superseded_by=new_id) and record new_id
        as superseding it; atomic with rollback on failure."""
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        for ident in (old_id, new_id):
            try:
                exists = store.exists(ident)
            except FormError as e:
                raise ToolError(str(e)) from None
            if not exists:
                raise ToolError(f"not found: {ident}")

        old_original_text = store.path_for(old_id).read_text(encoding="utf-8")

        try:
            old = store.update(
                old_id,
                attributes={STATUS_KEY: "Superseded", SUPERSEDED_BY_KEY: new_id},
                normalize=_adr_normalize,
            )
        except (FormError, ValueError) as e:
            raise ToolError(str(e)) from e
        try:
            new = store.update(
                new_id,
                attributes={SUPERSEDES_KEY: old_id},
                normalize=_adr_normalize,
            )
        except Exception as exc:
            store.atomic_write(store.path_for(old_id), old_original_text)
            raise ToolError(str(exc)) from exc
        sha = vcs.commit_paths(
            root,
            [store.path_for(old_id), store.path_for(new_id)],
            f"supersede adr {old_id} -> {new_id}",
        )

        return {
            "superseded": _entity_to_dict(old),
            "superseding": _entity_to_dict(new),
            "commit": sha,
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
        """Return ADRs whose attributes match `criteria`.

        `criteria` has the shape `{key: [values]}`: each key maps to a list of accepted
        values. Matching is within-key OR, across-key AND — a record matches a key if its
        attribute equals ANY listed value, and must match every key given. Matching is
        type-strict: a stored `1.0` is not matched by `1`, and `bool`/`int` never
        cross-match, so pass correctly-typed values.
        """
        store = _resolve_store(provider, project)
        entities, _ = store.load_all(normalize=_adr_normalize)
        matched = query_entities(entities, criteria or {})
        return {"items": [_entity_to_dict(e) for e in matched]}

    @mcp.tool(annotations={"readOnlyHint": True})
    def search(
        text: str,
        project: str = "",
        include_body: bool = False,
    ) -> ItemsResult:
        """Case-insensitive full-text search over ADR body and
        attributes.  When ``include_body`` is False (default), the ``body``
        field is omitted from each item."""
        store = _resolve_store(provider, project)
        entities, _ = store.load_all(normalize=_adr_normalize)
        matched = [e for e in entities if _entity_matches_text(e, text)]
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
        """Scoped, literal string replacement inside an ADR's body.

        Replaces exactly one occurrence of ``old`` with ``new``.
        """
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        try:
            entity = store.get(id, normalize=_adr_normalize)
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
            updated = store.update(id, body=new_body, normalize=_adr_normalize)
        except (FormError, ValueError) as e:
            raise ToolError(str(e)) from e
        sha = vcs.commit_paths(root, [store.path_for(id)], f"patch_body adr {id}")

        return {"item": _entity_to_dict(updated), "commit": sha}

    @mcp.tool(annotations={"destructiveHint": False})
    def commit(
        ids: Annotated[
            list[str], Field(description="List of ADR ids to stage and commit together.")
        ],
        message: Annotated[str, Field(description="Commit message for the checkpoint.")],
        project: str = "",
    ) -> CommitResult:
        """Stage and commit the named ADR files."""
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        for i in ids:
            if not store.exists(i):
                raise ToolError(f"not found: {i}")
        paths = [store.path_for(i) for i in ids]
        sha = vcs.commit_paths(root, paths, message)
        return {"ok": True, "commit": sha, "ids": ids}

    @mcp.tool(annotations={"readOnlyHint": True})
    def history(
        id: str,
        project: str = "",
        limit: Annotated[
            int, Field(description="Maximum number of commits to return (newest first).")
        ] = 20,
    ) -> CommitsResult:
        """Return the git commit history for a single ADR file."""
        store = _resolve_store(provider, project)
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
        """Return the unified diff for an ADR file.

        With no refs (the default), shows the last commit that touched this
        file versus its parent (or initial addition for a first commit).
        """
        store = _resolve_store(provider, project)
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
        ref: Annotated[str, Field(description="Git ref or sha to restore the ADR's content from.")],
        project: str = "",
    ) -> ItemCommitResult:
        """Restore an ADR to its contents at *ref* and commit forward.

        History is never rewritten.
        """
        store = _resolve_store(provider, project)
        root = _require_repo(store)
        if not vcs.path_in_history(root, store.path_for(id)):
            raise ToolError(f"not found: {id}")
        entity_path = store.path_for(id)
        content = vcs.read_at_ref(root, entity_path, ref)
        store.atomic_write(entity_path, content)
        sha = vcs.commit_paths(root, [entity_path], f"revert adr {id} to {ref}")
        return {"item": _entity_to_dict(store.get(id, normalize=_adr_normalize)), "commit": sha}

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

ADR_DIR = os.environ.get("ADR_DIR", str(Path.home() / ".micro_entity_adr"))
_provider = StoreProvider(
    Path(ADR_DIR),
    resolve_segment(explicit=None, workspace=os.getcwd()),
)
mcp = build_server(_provider)

if __name__ == "__main__":
    mcp.run()
