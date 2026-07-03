# pyright: reportOptionalSubscript=false, reportOperatorIssue=false, reportOptionalMemberAccess=false
import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.todo_server.conftest import _client


def _keys(rc) -> set[str]:
    """Top-level keys of a tool result's structured content."""
    return set(_tc(dict, rc.structured_content).keys())


# ---------------------------------------------------------------------------
# Create with progress
# ---------------------------------------------------------------------------


def test_create_empty_partition_has_progress(tmp_path: Path) -> None:
    """Create on empty partition: progress is {done:0, total:1}."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "buy milk", "attributes": {}})

    r = asyncio.run(go())
    assert "progress" in _keys(r)
    assert _tc(dict, r.structured_content)["progress"] == {"done": 0, "total": 1}


def test_create_progress_counts_total(tmp_path: Path) -> None:
    """Creating 3 todos: each create's progress reflects after-creation counts."""

    async def go():
        async with _client(tmp_path) as c:
            r1 = await c.call_tool("create", {"body": "one", "attributes": {}})
            r2 = await c.call_tool("create", {"body": "two", "attributes": {}})
            r3 = await c.call_tool("create", {"body": "three", "attributes": {}})
        return r1, r2, r3

    r1, r2, r3 = asyncio.run(go())
    assert _tc(dict, r1.structured_content)["progress"] == {"done": 0, "total": 1}
    assert _tc(dict, r2.structured_content)["progress"] == {"done": 0, "total": 2}
    assert _tc(dict, r3.structured_content)["progress"] == {"done": 0, "total": 3}


# ---------------------------------------------------------------------------
# Update with progress (common tool for todo)
# ---------------------------------------------------------------------------


def test_update_done_has_progress(tmp_path: Path) -> None:
    """Create 3 todos, update one to done: update's progress is {done:1, total:3}."""

    async def go():
        async with _client(tmp_path) as c:
            c1 = await c.call_tool("create", {"body": "one", "attributes": {}})
            await c.call_tool("create", {"body": "two", "attributes": {}})
            await c.call_tool("create", {"body": "three", "attributes": {}})
            tid = _tc(dict, c1.structured_content)["item"]["id"]
            return await c.call_tool("update", {"id": tid, "status": "done"})

    r = asyncio.run(go())
    assert "progress" in _keys(r)
    assert _tc(dict, r.structured_content)["progress"] == {"done": 1, "total": 3}


# ---------------------------------------------------------------------------
# Delete with progress
# ---------------------------------------------------------------------------


def test_delete_has_progress_drops_total(tmp_path: Path) -> None:
    """Create 3 todos, delete one: delete's progress has total drop."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "one", "attributes": {}})
            c2 = await c.call_tool("create", {"body": "two", "attributes": {}})
            await c.call_tool("create", {"body": "three", "attributes": {}})
            tid = _tc(dict, c2.structured_content)["item"]["id"]
            return await c.call_tool("delete", {"id": tid})

    r = asyncio.run(go())
    assert "progress" in _keys(r)
    assert _tc(dict, r.structured_content)["progress"] == {"done": 0, "total": 2}


# ---------------------------------------------------------------------------
# Patch body with progress
# ---------------------------------------------------------------------------


def test_patch_body_has_progress(tmp_path: Path) -> None:
    """Create 3 todos, patch body: result includes progress."""

    async def go():
        async with _client(tmp_path) as c:
            c1 = await c.call_tool("create", {"body": "buy milk", "attributes": {}})
            await c.call_tool("create", {"body": "walk dog", "attributes": {}})
            await c.call_tool("create", {"body": "fix leak", "attributes": {}})
            tid = _tc(dict, c1.structured_content)["item"]["id"]
            return await c.call_tool(
                "patch_body",
                {"id": tid, "old": "milk", "new": "eggs"},
            )

    r = asyncio.run(go())
    assert "progress" in _keys(r)
    assert _tc(dict, r.structured_content)["progress"] == {"done": 0, "total": 3}


# ---------------------------------------------------------------------------
# Revert with progress
# ---------------------------------------------------------------------------


def test_revert_has_progress(tmp_path: Path) -> None:
    """Create a todo, update it, revert: result includes progress."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "original", "attributes": {}})
            tid = _tc(dict, created.structured_content)["item"]["id"]
            await c.call_tool("update", {"id": tid, "body": "changed"})
            # Get history to find first commit sha for revert
            hist = await c.call_tool("history", {"id": tid, "limit": 20})
            hist_dict = _tc(dict, hist.structured_content)
            commits = _tc(list, hist_dict["commits"])
            ref = commits[-1]["sha"]  # first commit
            return await c.call_tool("revert", {"id": tid, "ref": ref})

    r = asyncio.run(go())
    assert "progress" in _keys(r)
    assert _tc(dict, r.structured_content)["progress"] == {"done": 0, "total": 1}
