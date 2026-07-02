import asyncio
import shutil
import tempfile
from pathlib import Path

from fastmcp import Client

from micro_entity import vcs
from micro_entity.partition import StoreProvider
from servers.todo import build_server
from tests.todo_server.conftest import _client

# ---------------------------------------------------------------------------
# Test 1 — revert restores STATE_A, commits forward, history preserved
# ---------------------------------------------------------------------------


def test_revert_restores_content_and_commits_forward(tmp_path: Path) -> None:
    """Create a todo with body "STATE_A" (commit A), update to "STATE_B"
    (commit B), then revert to HEAD~1: body must be STATE_A again, a new
    forward commit must appear, and the B-state commit must still exist."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "STATE_A", "attributes": {}},
            )
            item_id = created.data["item"]["id"]

            updated = await c.call_tool("update", {"id": item_id, "body": "STATE_B"})
            assert updated.data["item"]["body"] == "STATE_B", (
                f"expected STATE_B after update, got {updated.data['item']['body']!r}"
            )

            reverted = await c.call_tool("revert", {"id": item_id, "ref": "HEAD~1"})
            return item_id, reverted.data, created.data["item"]["body"]

    item_id, reverted, _ = asyncio.run(go())

    # The reverted item body is STATE_A again
    assert "STATE_A" in reverted["item"]["body"], (
        f"expected STATE_A in body, got {reverted['item']['body']!r}"
    )

    # On-disk file body is STATE_A
    entity_file = tmp_path / "test" / f"{item_id}.md"
    content = entity_file.read_text()
    assert "STATE_A" in content, f"on-disk body doesn't contain STATE_A:\n{content}"

    # Forward commit was created: newest message matches
    root = vcs.find_repo_root(tmp_path)
    log = vcs.file_log(root, tmp_path / "test" / f"{item_id}.md", limit=10)
    assert len(log) >= 2, f"expected at least 2 commits, got {len(log)}"
    msg = log[0]["message"]
    assert "revert todo" in msg, f"expected revert message, got {msg!r}"

    # The "update todo" commit (B state) still appears in history
    update_messages = [c["message"] for c in log if "update todo" in c["message"]]
    assert len(update_messages) >= 1, "B-state update commit disappeared (history was rewritten)"


# ---------------------------------------------------------------------------
# Test 2 — revert to current HEAD is no-op, still returns the item
# ---------------------------------------------------------------------------


def test_revert_to_head_is_noop_returns_item(tmp_path: Path) -> None:
    """Create a todo, then revert(id, HEAD): returns item with current body,
    no new commit is required (log count may be unchanged)."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "current content", "attributes": {}},
            )
            item_id = created.data["item"]["id"]

            reverted = await c.call_tool("revert", {"id": item_id, "ref": "HEAD"})
            return item_id, reverted.data

    item_id, reverted = asyncio.run(go())

    assert "current content" in reverted["item"]["body"], (
        f"expected 'current content' in body, got {reverted['item']['body']!r}"
    )

    # On-disk body matches
    entity_file = tmp_path / "test" / f"{item_id}.md"
    assert "current content" in entity_file.read_text()


# ---------------------------------------------------------------------------
# Test 3 — non-git store raises ToolError
# ---------------------------------------------------------------------------


def test_revert_non_git_store_raises(tmp_path: Path) -> None:
    """A store outside any git repo raises ToolError containing
    'storage is not under git'."""
    nogit = Path(tempfile.mkdtemp())
    try:
        server = build_server(StoreProvider(nogit, "test"))
        async def go_inner():
            async with Client(server) as c:
                return await c.call_tool(
                    "revert", {"id": "0001", "ref": "HEAD"}, raise_on_error=False
                )

        result = asyncio.run(go_inner())
        assert result.is_error is True
        content_list = result.content or []
        errmsg = (
            content_list[0].text if content_list and content_list[0].type == "text" else ""
        )
        assert "storage is not under git" in errmsg
    finally:
        shutil.rmtree(nogit, ignore_errors=True)
