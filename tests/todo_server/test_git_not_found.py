"""Tests that the four git-layer tools raise ToolError("not found: <id>")
for ids that were never created, and that historical ids still work with
history / diff / revert."""

import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client  # noqa: F401

# ---------------------------------------------------------------------------
# 1. history on a never-created id → ToolError
# ---------------------------------------------------------------------------


def test_history_not_found(tmp_path: Path) -> None:
    """history() with an id that was never created raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            with pytest.raises(ToolError) as exc:
                await c.call_tool("history", {"id": "9999"})
            assert "not found: 9999" in str(exc.value)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# 2. diff on a never-created id → ToolError
# ---------------------------------------------------------------------------


def test_diff_not_found(tmp_path: Path) -> None:
    """diff() with an id that was never created raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            with pytest.raises(ToolError) as exc:
                await c.call_tool("diff", {"id": "9999"})
            assert "not found: 9999" in str(exc.value)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# 3. revert on a never-created id → ToolError
# ---------------------------------------------------------------------------


def test_revert_not_found(tmp_path: Path) -> None:
    """revert() with an id that was never created raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            with pytest.raises(ToolError) as exc:
                await c.call_tool("revert", {"id": "9999", "ref": "HEAD"})
            assert "not found: 9999" in str(exc.value)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# 4. deleted-but-historical id STILL works with history
# ---------------------------------------------------------------------------


def test_history_deleted_id_still_works(tmp_path: Path) -> None:
    """Create a todo, delete it (auto-commits), then history(that_id)
    returns commits — not a not-found error."""

    async def go():
        async with _client(tmp_path) as c:
            # Create → auto-committed
            created = await c.call_tool(
                "create",
                {"body": "will be deleted"},
            )
            item_id = (_tc(dict, created.structured_content))["item"]["id"]

            # Delete → auto-commits deletion
            await c.call_tool("delete", {"id": item_id})

            # History should return commits (create + delete), NOT a 404
            result = await c.call_tool("history", {"id": item_id})
            return (_tc(dict, result.structured_content))["commits"], item_id

    commits, item_id = asyncio.run(go())
    assert len(commits) >= 2, f"expected create+delete commits, got {len(commits)}: {commits}"
    has_create = any("create todo" in c["message"] for c in commits)
    has_delete = any("delete todo" in c["message"] for c in commits)
    assert has_create, f"no 'create todo' in commits: {commits}"
    assert has_delete, f"no 'delete todo' in commits: {commits}"


# ---------------------------------------------------------------------------
# 6. deleted id STILL works with revert
# ---------------------------------------------------------------------------


def test_revert_deleted_id_still_works(tmp_path: Path) -> None:
    """Create a todo, update it, delete it. revert to the update commit
    should restore the entity (revert reads from git history, not from store).

    Note: after revert the entity file is written back to disk, so the
    entity becomes readable again."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "STATE_A"},
            )
            item_id = (_tc(dict, created.structured_content))["item"]["id"]

            await c.call_tool(
                "update",
                {"id": item_id, "body": "STATE_B"},
            )

            await c.call_tool("delete", {"id": item_id})

            # Revert to the update commit (HEAD~1 at the time = STATE_B)
            result = await c.call_tool(
                "revert",
                {"id": item_id, "ref": "HEAD~1"},
            )
            return (_tc(dict, result.structured_content))["item"]["body"], item_id

    body, item_id = asyncio.run(go())
    assert "STATE_B" in body, f"expected STATE_B, got {body!r}"


# ---------------------------------------------------------------------------
# 7. deleted id STILL works with diff
# ---------------------------------------------------------------------------


def test_diff_deleted_id_still_works(tmp_path: Path) -> None:
    """Create, update, delete. diff(id, ref=HEAD~1, to=HEAD) should
    return the diff between the two historical states — no not-found."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "original"})
            # Need at least 2 commits total for HEAD~1
            await c.call_tool(
                "update",
                {"id": "0001", "status": "in-progress"},
            )

            result = await c.call_tool(
                "diff",
                {"id": "0001", "ref": "HEAD~1", "to": "HEAD"},
            )
            return (_tc(dict, result.structured_content))["diff"]

    diff_text = asyncio.run(go())
    assert isinstance(diff_text, str)


# ---------------------------------------------------------------------------
# 8. Valid existing ids still work — no regression
# ---------------------------------------------------------------------------


def test_history_valid_id_still_works(tmp_path: Path) -> None:
    """history on a valid existing id returns commits (no regression)."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "regression test"})
            result = await c.call_tool("history", {"id": "0001"})
            return (_tc(dict, result.structured_content))["commits"]

    commits = asyncio.run(go())
    assert len(commits) >= 1


def test_diff_valid_id_still_works(tmp_path: Path) -> None:
    """diff on a valid existing id returns {diff: ...} (no regression)."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "regression diff"})
            result = await c.call_tool(
                "diff",
                {"id": "0001", "ref": "HEAD", "to": "HEAD"},
            )
            return (_tc(dict, result.structured_content))["diff"]

    diff_text = asyncio.run(go())
    assert diff_text == ""  # same ref → empty


def test_revert_valid_id_still_works(tmp_path: Path) -> None:
    """revert on a valid existing id with ref=HEAD no-ops cleanly."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "revert-me"},
            )
            item_id = (_tc(dict, created.structured_content))["item"]["id"]
            result = await c.call_tool(
                "revert",
                {"id": item_id, "ref": "HEAD"},
            )
            return (_tc(dict, result.structured_content))["item"]["body"]

    body = asyncio.run(go())
    assert "revert-me" in body
