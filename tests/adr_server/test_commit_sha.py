"""Tests that every committing ADR tool returns a ``commit`` sha key.

Additive key — all existing keys stay exactly as before.
"""

import asyncio
from pathlib import Path

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
                    "id": "ADR-SHA1",
                    "title": "Sha test create",
                    "body": "prose",
                },
            )

    r = asyncio.run(go())
    data = r.data
    assert "item" in data
    item = data["item"]
    assert item["id"] == "ADR-SHA1"
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
                {"id": "ADR-SHA2", "title": "Sha test update", "body": "state_a"},
            )
            return await c.call_tool(
                "update",
                {"id": "ADR-SHA2", "status": "Accepted"},
            )

    r = asyncio.run(go())
    data = r.data
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
                {"id": "ADR-SHA3", "title": "Sha test patch", "body": "old word"},
            )
            return await c.call_tool(
                "patch_body",
                {"id": "ADR-SHA3", "old": "old", "new": "new"},
            )

    r = asyncio.run(go())
    data = r.data
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
                {"id": "ADR-SHA4", "title": "Sha test revert", "body": "STATE_A"},
            )
            await c.call_tool(
                "update",
                {"id": "ADR-SHA4", "body": "STATE_B"},
            )
            return await c.call_tool(
                "revert",
                {"id": "ADR-SHA4", "ref": "HEAD~1"},
            )

    r = asyncio.run(go())
    data = r.data
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
                {"id": "ADR-SHA5A", "title": "Old", "body": "old body"},
            )
            await c.call_tool(
                "create",
                {"id": "ADR-SHA5B", "title": "New", "body": "new body"},
            )
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-SHA5A", "new_id": "ADR-SHA5B"},
            )

    r = asyncio.run(go())
    data = r.data
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
                {"id": "ADR-SHA6", "title": "Get test", "body": "body"},
            )
            return await c.call_tool("get", {"id": "ADR-SHA6"})

    r = asyncio.run(go())
    data = r.data
    assert "item" in data
    assert "commit" not in data
