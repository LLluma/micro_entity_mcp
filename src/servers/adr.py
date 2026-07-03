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
from micro_entity.markdown_store import UNSET as UNSET
from micro_entity.markdown_store import MarkdownStore
from micro_entity.partition import (
    StoreProvider,
    resolve_segment,
)
from micro_entity.validation import FormError, validate_against_set
from servers._common import (
    ProfileConfig,
    _entity_to_dict,
    _require_repo,
    _resolve_store,
    register_common_tools,
)
from servers.schemas import ItemCommitResult, SupersedeResult

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

A read issued in the same parallel batch as a write may not observe that write;
sequence dependent calls rather than batching a read with its write.

A missing id fails with "not found: {id}".
"""

STATUS_VALUES: set[str] = {"Proposed", "Accepted", "Superseded"}
STATUS_KEY: str = "status"
SUPERSEDES_KEY: str = "supersedes"
SUPERSEDED_BY_KEY: str = "superseded_by"
DEFAULT_STATUS: str = "Proposed"
RESERVED_KEYS: frozenset[str] = frozenset({"created", "updated", "id"})


# ---------------------------------------------------------------------------
# Helpers (adr-specific)
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
# Factory — the testability seam
# ---------------------------------------------------------------------------


def build_server(provider: StoreProvider) -> FastMCP:
    """Build the FastMCP server for the ADR profile.

    Common tools come from the shared scaffold; only ``create`` and
    ``supersede`` are adr-specific.
    """
    cfg = ProfileConfig(
        name="adr",
        instructions=ADR_INSTRUCTIONS,
        status_values=STATUS_VALUES,
        normalize=_adr_normalize,
        normalize_id=_normalize_adr_id,
        reserved_keys=RESERVED_KEYS,
    )
    mcp = FastMCP("adr", instructions=ADR_INSTRUCTIONS)
    register_common_tools(mcp, provider, cfg)

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

    @mcp.tool(annotations={"destructiveHint": True})
    def supersede(old_id: str, new_id: str, project: str = "") -> SupersedeResult:
        """Mark old_id Superseded (superseded_by=new_id) and record new_id
        as superseding it; atomic with rollback on failure."""
        store = _resolve_store(provider, project)
        old_id = store.normalize_id(old_id)
        new_id = store.normalize_id(new_id)
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

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

ADR_DIR = os.environ.get("ADR_DIR", str(Path.home() / ".micro_entity_adr"))
_provider = StoreProvider(
    Path(ADR_DIR),
    resolve_segment(explicit=None, workspace=os.getcwd()),
    normalize_id=_normalize_adr_id,
)
mcp = build_server(_provider)

if __name__ == "__main__":
    mcp.run()
