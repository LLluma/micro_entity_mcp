"""Issue profile server — exposes issue tracking via FastMCP."""

import os
import re
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from micro_entity import vcs
from micro_entity.markdown_store import MarkdownStore
from micro_entity.partition import StoreProvider, resolve_segment
from micro_entity.store import NotFoundError
from micro_entity.validation import FormError, validate_against_set
from servers._common import (
    ProfileConfig,
    _entity_to_dict,
    _require_repo,
    _resolve_store,
    register_common_tools,
)
from servers.schemas import ItemCommitResult, OkIdCommitResult

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

ISSUE_INSTRUCTIONS = """\
Issue profile: durable "what happened" records — observations and bugs that are
mutable and closeable but never deleted. Ids are server-assigned, sequential and
zero-padded (ISSUE-NNNN); statuses are open / closed / wontfix (open is the
default and the only non-terminal state). A wrong or duplicate report is closed
as wontfix, never deleted.

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

STATUS_VALUES: set[str] = {"open", "closed", "wontfix"}
STATUS_KEY: str = "status"
DEFAULT_STATUS: str = "open"
RESERVED_KEYS: frozenset[str] = frozenset({"created", "updated", "id"})


# ---------------------------------------------------------------------------
# Helpers (issue-specific)
# ---------------------------------------------------------------------------


_issue_id_re = re.compile(r"^[Ii][Ss][Ss][Uu][Ee]-?(\d+)$")


def _normalize_issue_id(raw: str) -> str:
    """Canonicalize *raw* to ``ISSUE-NNNN`` form.

    All-digits strings are treated as a bare ordinal (``"7"`` -> ``"ISSUE-0007"``).
    Any casing of ``ISSUE``, optionally followed by ``-``, then digits, is
    normalised (e.g. ``"issue-7"``, ``"Issue7"`` -> ``"ISSUE-0007"``).
    Anything else is returned unchanged.

    Idempotent: ``_normalize_issue_id(_normalize_issue_id(s)) == _normalize_issue_id(s)``.
    """
    if raw.isdigit():
        return f"ISSUE-{int(raw):04d}"
    m = _issue_id_re.match(raw)
    if m:
        return f"ISSUE-{int(m.group(1)):04d}"
    return raw


_next_issue_re = re.compile(r"^ISSUE-(\d+)$")


def _next_issue_id(store: MarkdownStore) -> str:
    """Return the next ISSUE id based on existing records."""
    entities, _ = store.load_all()
    max_n = 0
    for e in entities:
        m = _next_issue_re.match(e.id)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"ISSUE-{max_n + 1:04d}"


# ---------------------------------------------------------------------------
# Factory — the testability seam
# ---------------------------------------------------------------------------


def build_server(provider: StoreProvider) -> FastMCP:
    """Build the FastMCP server for the issue profile.

    Common tools come from the shared scaffold; only ``create`` is
    issue-specific. There is intentionally no delete/next/is_complete/supersede.
    """
    cfg = ProfileConfig(
        name="issue",
        instructions=ISSUE_INSTRUCTIONS,
        status_values=STATUS_VALUES,
        normalize=None,
        normalize_id=_normalize_issue_id,
        reserved_keys=RESERVED_KEYS,
    )
    mcp = FastMCP("issue", instructions=ISSUE_INSTRUCTIONS)
    register_common_tools(mcp, provider, cfg)

    @mcp.tool(annotations={"destructiveHint": False})
    def create(
        title: str,
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
        """Create an issue. The server assigns a sequential id (ISSUE-NNNN);
        default status is "open"."""
        store = _resolve_store(provider, project)
        new_id = _next_issue_id(store)
        attrs = dict(attributes) if attributes else {}
        bad = RESERVED_KEYS & attrs.keys()
        if bad:
            raise ToolError(f"cannot set reserved keys: {sorted(bad)}")
        attrs["title"] = title
        if status is not None:
            attrs[STATUS_KEY] = status
        status = attrs.get(STATUS_KEY) or DEFAULT_STATUS
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
        sha = vcs.commit_paths(root, [store.path_for(new_id)], f"create issue {new_id}")

        return {"item": _entity_to_dict(entity), "commit": sha}

    @mcp.tool(annotations={"destructiveHint": True, "idempotentHint": True})
    def delete(id: str, project: str = "") -> OkIdCommitResult:
        """Delete an issue entity by id."""
        store = _resolve_store(provider, project)
        id = store.normalize_id(id)
        root = _require_repo(store)
        try:
            store.delete(id)
        except NotFoundError as e:
            raise ToolError(f"not found: {id}") from e
        sha = vcs.commit_paths(root, [store.path_for(id)], f"delete issue {id}")
        return {"ok": True, "id": id, "commit": sha}  # type: ignore[return-value]

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

ISSUE_DIR = os.environ.get("ISSUE_DIR", str(Path.home() / ".micro_entity_issue"))
_provider = StoreProvider(
    Path(ISSUE_DIR),
    resolve_segment(explicit=None, workspace=os.getcwd()),
    normalize_id=_normalize_issue_id,
)
mcp = build_server(_provider)

if __name__ == "__main__":
    mcp.run()
