"""Tests that the four git-layer tools raise ToolError("not found: <id>") for bad ids.

Mirrors what was already done on the todo server (test_git_not_found.py).
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import cast as _tc

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
# regression — valid existing id still works (history)
# ---------------------------------------------------------------------------


def test_history_valid_id_still_works(tmp_path: Path) -> None:
    """existing id still returns commits as before."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "B"})
            r = await c.call_tool("history", {"id": "ADR-0001"})
        assert len((_tc(dict, r.structured_content))["commits"]) >= 1

    asyncio.run(go())


def test_history_update_then_history_works(tmp_path: Path) -> None:
    """create + update → history returns multiple commits."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "B"})
            await c.call_tool("update", {"id": "ADR-0001", "body": "B1"})
            await c.call_tool("update", {"id": "ADR-0001", "body": "B2"})
            r = await c.call_tool("history", {"id": "ADR-0001"})
        assert len((_tc(dict, r.structured_content))["commits"]) == 3
        assert "update adr ADR-0001" in (_tc(dict, r.structured_content))["commits"][0]["message"]

    asyncio.run(go())


# ---------------------------------------------------------------------------
# regression — valid existing id still works (diff)
# ---------------------------------------------------------------------------


def test_diff_valid_id_still_works(tmp_path: Path) -> None:
    """existing id still returns diff."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "ORIGINAL"})
            # dirty the working tree
            r = await c.call_tool("diff", {"id": "ADR-0001", "ref": "HEAD"})
        assert isinstance((_tc(dict, r.structured_content))["diff"], str)
        # no dirty yet → empty diff

    asyncio.run(go())


# ---------------------------------------------------------------------------
# regression — valid existing id still works (revert)
# ---------------------------------------------------------------------------


def test_revert_valid_id_still_works(tmp_path: Path) -> None:
    """existing id revert still works and returns restored item."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "STATE_A"})
            await c.call_tool("update", {"id": "ADR-0001", "body": "STATE_B"})
            r = await c.call_tool("revert", {"id": "ADR-0001", "ref": "HEAD~1"})
        assert "STATE_A" in (_tc(dict, r.structured_content))["item"]["body"]

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
