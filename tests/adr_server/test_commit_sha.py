"""Tests that every committing ADR tool returns a ``commit`` sha key.

Additive key — all existing keys stay exactly as before.
"""

import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.adr_server.conftest import _client

# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_returns_commit_sha(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "Sha test create",
                    "body": "prose",
                },
            )

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert "item" in data
    item = data["item"]
    assert item["id"] == "ADR-0001"
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_returns_commit_sha(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "Sha test update", "body": "state_a"},
            )
            return await c.call_tool(
                "update",
                {"id": "ADR-0001", "status": "Accepted"},
            )

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert "item" in data
    assert data["item"]["attributes"]["status"] == "Accepted"
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# patch_body
# ---------------------------------------------------------------------------


def test_patch_body_returns_commit_sha(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "Sha test patch", "body": "old word"},
            )
            return await c.call_tool(
                "patch_body",
                {"id": "ADR-0001", "old": "old", "new": "new"},
            )

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert "item" in data
    assert data["item"]["body"] == "new word"
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# revert
# ---------------------------------------------------------------------------


def test_revert_returns_commit_sha(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "Sha test revert", "body": "STATE_A"},
            )
            await c.call_tool(
                "update",
                {"id": "ADR-0001", "body": "STATE_B"},
            )
            return await c.call_tool(
                "revert",
                {"id": "ADR-0001", "ref": "HEAD~1"},
            )

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert "item" in data
    assert "STATE_A" in data["item"]["body"]
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# supersede
# ---------------------------------------------------------------------------


def test_supersede_returns_commit_sha(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "Old", "body": "old body"},
            )
            await c.call_tool(
                "create",
                {"title": "New", "body": "new body"},
            )
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-0001", "new_id": "ADR-0002"},
            )

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert "superseded" in data
    assert "superseding" in data
    assert data["superseded"]["attributes"]["status"] == "Superseded"
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# get — must NOT have commit key
# ---------------------------------------------------------------------------


def test_get_returns_no_commit_key(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "Get test", "body": "body"},
            )
            return await c.call_tool("get", {"id": "ADR-0001"})

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert "item" in data
    assert "commit" not in data
