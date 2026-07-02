"""Tests for the ``history`` tool on the todo server."""

import asyncio
import shutil
import tempfile
from pathlib import Path

from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.todo import build_server
from tests.todo_server.conftest import _client


def test_history_returns_commits_after_create_and_updates(
    tmp_path: Path,
) -> None:
    """Create a todo then update it twice — 3 mutations → 3 commits.

    Assert newest‑first ordering, non‑empty sha, date and message.
    """

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "history test body"},
            )
            item_id = created.data["item"]["id"]

            await c.call_tool("update", {"id": item_id, "status": "in-progress"})
            await c.call_tool("update", {"id": item_id, "status": "done"})

            result = await c.call_tool("history", {"id": item_id})
            return result.data["commits"], item_id

    commits, item_id = asyncio.run(go())
    assert len(commits) == 3, f"Expected 3 commits, got {len(commits)}"

    # Newest first — last update should be first record
    assert commits[0]["message"] == f"update todo {item_id}"

    # Every record has non-empty sha, date, message
    for record in commits:
        assert "sha" in record and len(record["sha"]) > 0
        assert "date" in record and len(record["date"]) > 0
        assert "message" in record and len(record["message"]) > 0

    # Verify ordering: commit 0 = update, commit 1 = update, commit 2 = create
    assert commits[1]["message"] == f"update todo {item_id}"
    assert commits[2]["message"] == f"create todo {item_id}"


def test_history_limit_caps_results(tmp_path: Path) -> None:
    """history(id, limit=1) returns exactly 1 record even after 3 mutations."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "limit test"},
            )
            item_id = created.data["item"]["id"]

            await c.call_tool("update", {"id": item_id, "status": "in-progress"})
            await c.call_tool("update", {"id": item_id, "status": "done"})

            result = await c.call_tool("history", {"id": item_id, "limit": 1})
            return result.data["commits"]

    commits = asyncio.run(go())
    assert len(commits) == 1


def test_history_non_git_store_raises() -> None:
    """Build server on a non-git directory — history raises ToolError."""
    nogit = tempfile.mkdtemp()
    try:

        async def go():
            server = build_server(StoreProvider(Path(nogit), "test"))
            async with Client(server) as c:
                r = await c.call_tool(
                    "history",
                    {"id": "0001"},
                    raise_on_error=False,
                )
                return r

        r = asyncio.run(go())
        assert r.is_error is True
        error_str = str(r.data if hasattr(r, "data") and r.data else r)
        assert "storage is not under git" in error_str
    finally:
        shutil.rmtree(nogit, ignore_errors=True)
