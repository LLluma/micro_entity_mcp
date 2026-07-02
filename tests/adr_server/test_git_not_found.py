"""Tests that the four git-layer tools raise ToolError("not found: <id>") for bad ids.

Mirrors what was already done on the todo server (test_git_not_found.py).
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client

# ---------------------------------------------------------------------------
# history — id never created
# ---------------------------------------------------------------------------


def test_history_nonexistent_id_raises_not_found(tmp_path: Path) -> None:
    """calling history with an id that was never committed → ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            # No ADR created — the id was never committed to git history.
            with pytest.raises(ToolError) as exc:
                await c.call_tool("history", {"id": "ADR-9999"})
        assert "not found: ADR-9999" in str(exc.value)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# diff — id never created
# ---------------------------------------------------------------------------


def test_diff_nonexistent_id_raises_not_found(tmp_path: Path) -> None:
    """calling diff with an id that was never committed to git history → ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            with pytest.raises(ToolError) as exc:
                await c.call_tool("diff", {"id": "ADR-9999"})
        assert "not found: ADR-9999" in str(exc.value)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# revert — id never created
# ---------------------------------------------------------------------------


def test_revert_nonexistent_id_raises_not_found(tmp_path: Path) -> None:
    """calling revert with an id that was never committed to git history → ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            with pytest.raises(ToolError) as exc:
                await c.call_tool("revert", {"id": "ADR-9999", "ref": "HEAD"})
        assert "not found: ADR-9999" in str(exc.value)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# commit — id never created
# ---------------------------------------------------------------------------


def test_commit_nonexistent_id_raises_not_found(tmp_path: Path) -> None:
    """calling commit with a nonexistent id → ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            with pytest.raises(ToolError) as exc:
                await c.call_tool("commit", {"ids": ["ADR-9999"], "message": "nope"})
        assert "not found: ADR-9999" in str(exc.value)

    asyncio.run(go())


def test_commit_mixed_ids_nonexistent_raises_not_found(tmp_path: Path) -> None:
    """commit with one real + one nonexistent id → ToolError for the missing one."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0001", "title": "T", "body": "B"})
            with pytest.raises(ToolError) as exc:
                await c.call_tool("commit", {"ids": ["ADR-0001", "ADR-9999"], "message": "mixed"})
        assert "not found: ADR-9999" in str(exc.value)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# regression — valid existing id still works (history)
# ---------------------------------------------------------------------------


def test_history_valid_id_still_works(tmp_path: Path) -> None:
    """existing id still returns commits as before."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0001", "title": "T", "body": "B"})
            r = await c.call_tool("history", {"id": "ADR-0001"})
        assert len(r.data["commits"]) >= 1

    asyncio.run(go())


def test_history_update_then_history_works(tmp_path: Path) -> None:
    """create + update → history returns multiple commits."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0002", "title": "T", "body": "B"})
            await c.call_tool("update", {"id": "ADR-0002", "body": "B1"})
            await c.call_tool("update", {"id": "ADR-0002", "body": "B2"})
            r = await c.call_tool("history", {"id": "ADR-0002"})
        assert len(r.data["commits"]) == 3
        assert "update adr ADR-0002" in r.data["commits"][0]["message"]

    asyncio.run(go())


# ---------------------------------------------------------------------------
# regression — valid existing id still works (diff)
# ---------------------------------------------------------------------------


def test_diff_valid_id_still_works(tmp_path: Path) -> None:
    """existing id still returns diff."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0003", "title": "T", "body": "ORIGINAL"})
            # dirty the working tree
            r = await c.call_tool("diff", {"id": "ADR-0003", "ref": "HEAD"})
        assert isinstance(r.data["diff"], str)
        # no dirty yet → empty diff

    asyncio.run(go())


# ---------------------------------------------------------------------------
# regression — valid existing id still works (revert)
# ---------------------------------------------------------------------------


def test_revert_valid_id_still_works(tmp_path: Path) -> None:
    """existing id revert still works and returns restored item."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0004", "title": "T", "body": "STATE_A"})
            await c.call_tool("update", {"id": "ADR-0004", "body": "STATE_B"})
            r = await c.call_tool("revert", {"id": "ADR-0004", "ref": "HEAD~1"})
        assert "STATE_A" in r.data["item"]["body"]

    asyncio.run(go())


# ---------------------------------------------------------------------------
# regression — valid existing id still works (commit)
# ---------------------------------------------------------------------------


def test_commit_valid_id_still_works(tmp_path: Path) -> None:
    """existing id commit still works."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0005", "title": "T", "body": "B"})
            p = tmp_path / "seg" / "ADR-0005.md"
            p.write_text(p.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
            r = await c.call_tool("commit", {"ids": ["ADR-0005"], "message": "checkpoint"})
        assert r.data["ok"] is True
        assert r.data["commit"] is not None
        assert r.data["ids"] == ["ADR-0005"]

    asyncio.run(go())


def test_commit_no_dirty_still_works(tmp_path: Path) -> None:
    """commit with clean state still returns ok and commit=None."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0006", "title": "T", "body": "B"})
            r = await c.call_tool("commit", {"ids": ["ADR-0006"], "message": "noop"})
        assert r.data["ok"] is True
        assert r.data["commit"] is None

    asyncio.run(go())


# ---------------------------------------------------------------------------
# edge — non-git store still raises "not under git" (not "not found")
# ---------------------------------------------------------------------------


def test_history_non_git_store_raises_tool_error() -> None:
    """history on a non-git store raises a different error."""
    nogit = tempfile.mkdtemp()
    try:
        client = Client(build_server(StoreProvider(Path(nogit), "seg")))

        async def go():
            async with client:
                return await client.call_tool("history", {"id": "ADR-0001"}, raise_on_error=False)

        r = asyncio.run(go())
        assert r.is_error is True
    finally:
        shutil.rmtree(nogit, ignore_errors=True)
