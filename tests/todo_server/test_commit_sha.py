"""Verify that every committing tool returns an additive ``commit`` key
with the git SHA (str) or ``None`` on no-op."""

import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client

# ---------------------------------------------------------------------------
# create — returns {"item": ..., "commit": sha}
# ---------------------------------------------------------------------------


def test_create_returns_commit_sha(tmp_path: Path) -> None:
    """create() returns dict with 'item' AND 'commit'; commit is a non-empty sha."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "commit sha test", "attributes": {}})

    r = asyncio.run(go())
    data = r.data
    assert "item" in data
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# update — returns {"item": ..., "commit": sha}
# ---------------------------------------------------------------------------


def test_update_returns_commit_sha(tmp_path: Path) -> None:
    """update() returns dict with 'item' AND 'commit'; commit is a non-empty sha."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "update sha test", "attributes": {}})
            item_id = created.data["item"]["id"]
            updated = await c.call_tool("update", {"id": item_id, "status": "done"})
            return updated.data

    data = asyncio.run(go())
    assert "item" in data
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# patch_body — returns {"item": ..., "commit": sha}
# ---------------------------------------------------------------------------


def test_patch_body_returns_commit_sha(tmp_path: Path) -> None:
    """patch_body() returns dict with 'item' AND 'commit'; commit is a sha."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "patch old text", "attributes": {}})
            item_id = created.data["item"]["id"]
            patched = await c.call_tool("patch_body", {"id": item_id, "old": "old", "new": "new"})
            return patched.data

    data = asyncio.run(go())
    assert "item" in data
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# revert — returns {"item": ..., "commit": sha}
# ---------------------------------------------------------------------------


def test_revert_returns_commit_sha(tmp_path: Path) -> None:
    """revert() returns dict with 'item' AND 'commit'; commit is a sha."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "revert target body", "attributes": {}})
            # HEAD~1 is just "state before update" — revert should still
            # return the item with a forward commit sha.
            item_id = created.data["item"]["id"]
            # Update to create a diff then revert to HEAD~1 relative to head
            await c.call_tool("update", {"id": item_id, "body": "revert target body"})
            reverted = await c.call_tool("revert", {"id": item_id, "ref": "HEAD"})
            return reverted.data

    data = asyncio.run(go())
    assert "item" in data
    assert "commit" in data
    sha = data["commit"]
    assert sha is None or (isinstance(sha, str) and len(sha) > 0)


# ---------------------------------------------------------------------------
# delete — returns {"ok": True, "id": id, "commit": sha}
# ---------------------------------------------------------------------------


def test_delete_returns_commit_sha(tmp_path: Path) -> None:
    """delete() returns dict with 'ok', 'id' AND 'commit'; commit is a sha."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "delete sha test", "attributes": {}})
            item_id = created.data["item"]["id"]
            deleted = await c.call_tool("delete", {"id": item_id})
            return deleted.data, item_id

    data, item_id = asyncio.run(go())
    assert data["ok"] is True
    assert data["id"] == item_id
    assert "commit" in data
    sha = data["commit"]
    assert isinstance(sha, str)
    assert len(sha) > 0


# ---------------------------------------------------------------------------
# get — still returns just {"item": ...}, NO commit key
# ---------------------------------------------------------------------------


def test_get_no_commit_key(tmp_path: Path) -> None:
    """get() returns {'item': ...} with NO 'commit' key."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "get no commit", "attributes": {}})
            item_id = created.data["item"]["id"]
            return await c.call_tool("get", {"id": item_id})

    r = asyncio.run(go())
    assert "item" in r.data
    assert "commit" not in r.data
