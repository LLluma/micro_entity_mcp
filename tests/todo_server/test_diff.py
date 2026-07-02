# pyright: reportOptionalSubscript=false, reportOperatorIssue=false, reportOptionalMemberAccess=false

"""Tests for the ``diff`` tool on the todo server."""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import cast as _tc

from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.todo import build_server
from tests.todo_server.conftest import _client

# ---------------------------------------------------------------------------
# Diff between two refs (both committed)
# ---------------------------------------------------------------------------


def test_diff_returns_diff_between_created_and_updated(tmp_path: Path) -> None:
    """Create a todo with a known body, update to a distinctive body.
    diff(id, ref="HEAD~1", to="HEAD") must contain the new status/body."""

    async def go():
        async with _client(tmp_path) as c:
            r1 = await c.call_tool("create", {"body": "original body text"})
            idx = (_tc(dict, r1.structured_content))["item"]["id"]

            # Update to a distinctive status and body
            await c.call_tool(
                "update",
                {"id": idx, "status": "in-progress", "body": "CHANGED_BODY_XYZ"},
            )

            # diff HEAD~1 (create) vs HEAD (update)
            r = await c.call_tool(
                "diff",
                {"id": idx, "ref": "HEAD~1", "to": "HEAD"},
            )
            return r.structured_content

    structured_content = asyncio.run(go())
    diff_text = structured_content["diff"]
    assert diff_text != "", "diff between create and update must be non-empty"
    assert "CHANGED_BODY_XYZ" in diff_text
    assert "in-progress" in diff_text


def test_diff_same_refs_returns_empty(tmp_path: Path) -> None:
    """diff with identical refs returns empty string."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "same"})
            r = await c.call_tool(
                "diff",
                {"id": "0001", "ref": "HEAD", "to": "HEAD"},
            )
            return r.structured_content

    structured_content = asyncio.run(go())
    assert isinstance(structured_content, dict)
    assert structured_content["diff"] == ""


def test_diff_ref_works_tree(tmp_path: Path) -> None:
    """Create then update (both committed). diff(id, ref=HEAD~1, to=None)
    compares HEAD~1 tag to working tree (which is clean == HEAD)."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "original body"})
            await c.call_tool(
                "update",
                {"id": "0001", "status": "done"},
            )
            # ref=HEAD~1, to=None → HEAD~1 vs working tree (clean == HEAD)
            r = await c.call_tool(
                "diff",
                {"id": "0001", "ref": "HEAD~1", "to": None},
            )
            return r

    r = asyncio.run(go())
    diff_text = (_tc(dict, r.structured_content))["diff"]
    assert diff_text != "", "diff from HEAD~1 to WTP must be non-empty"


# ---------------------------------------------------------------------------
# No-ref defaults: last-change diff
# ---------------------------------------------------------------------------


def test_diff_no_args_returns_last_change(tmp_path: Path) -> None:
    """diff(id) with no ref args returns the last commit that touched the
    file. After create+update the diff must be non-empty."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "original body"})
            await c.call_tool(
                "update",
                {"id": "0001", "status": "in-progress", "body": "CHANGED_BODY_XYZ"},
            )
            r = await c.call_tool("diff", {"id": "0001"})
            return r.structured_content

    structured_content = asyncio.run(go())
    diff_text = structured_content["diff"]
    assert diff_text != "", "no-arg diff on updated todo must be non-empty (last change)"
    assert "CHANGED_BODY_XYZ" in diff_text


def test_diff_no_args_single_commit(tmp_path: Path) -> None:
    """diff(id) on a freshly created todo (1 commit) returns a non-empty
    diff showing its content as an addition."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "initial content"})
            r = await c.call_tool("diff", {"id": "0001"})
            return r.structured_content

    structured_content = asyncio.run(go())
    diff_text = structured_content["diff"]
    assert diff_text != "", "no-arg diff on single-commit todo must be non-empty"
    assert "initial content" in diff_text


# ---------------------------------------------------------------------------
# Non-git store raises ToolError
# ---------------------------------------------------------------------------


def test_non_git_store_raises() -> None:
    """Build on a non-git directory -- diff raises ToolError."""
    nogit = tempfile.mkdtemp()
    try:

        async def go():
            server = build_server(StoreProvider(Path(nogit), "test"))
            async with Client(server) as c:
                return await c.call_tool(
                    "diff",
                    {"id": "0001", "ref": "HEAD"},
                    raise_on_error=False,
                )

        r = asyncio.run(go())
        assert r.is_error is True
        error_str = str(
            r.structured_content if hasattr(r, "structured_content") and r.structured_content else r
        )
        assert "storage is not under git" in error_str
    finally:
        shutil.rmtree(nogit, ignore_errors=True)
