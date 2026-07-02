# pyright: reportOptionalSubscript=false, reportOperatorIssue=false, reportOptionalMemberAccess=false
import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import cast as _tc

from fastmcp import Client

from micro_entity import vcs
from micro_entity.partition import StoreProvider
from servers.todo import build_server
from tests.todo_server.conftest import _client


def test_commit_with_pending_changes_returns_sha(tmp_path: Path) -> None:
    """Create two todos, modify their files on disk, commit — assert sha and log."""

    async def go():
        async with _client(tmp_path) as c:
            # Create two todos (auto-committed, tree clean)
            r1 = await c.call_tool("create", {"body": "first"})
            r2 = await c.call_tool("create", {"body": "second"})
            id1 = (_tc(dict, r1.structured_content))["item"]["id"]
            id2 = (_tc(dict, r2.structured_content))["item"]["id"]

            # Make uncommitted changes on disk
            p1 = tmp_path / "test" / f"{id1}.md"
            p1.write_text(p1.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
            p2 = tmp_path / "test" / f"{id2}.md"
            p2.write_text(p2.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")

            # Commit them
            result = await c.call_tool("commit", {"ids": [id1, id2], "message": "checkpoint"})

            # Verify return shape
            assert (_tc(dict, result.structured_content))["ok"] is True
            assert isinstance((_tc(dict, result.structured_content))["commit"], str)
            assert len((_tc(dict, result.structured_content))["commit"]) > 0
            assert (_tc(dict, result.structured_content))["ids"] == [id1, id2]

            # Verify the commit message appears in the log
            root = vcs.find_repo_root(tmp_path)
            entries = vcs.file_log(root, tmp_path / "test" / f"{id1}.md", limit=5)
            assert entries[0]["message"] == "checkpoint"

            return result.structured_content

    structured_content = asyncio.run(go())
    assert structured_content["ok"] is True


def test_commit_no_pending_changes_returns_none(tmp_path: Path) -> None:
    """Create a todo (auto-committed), commit immediately — no changes, None sha."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "clean"})
            r = await c.call_tool("commit", {"ids": ["0001"], "message": "noop"})
            return r.structured_content

    structured_content = asyncio.run(go())
    assert structured_content["ok"] is True
    assert structured_content["commit"] is None
    assert structured_content["ids"] == ["0001"]


def test_non_git_store_raises() -> None:
    """Build server on a non-git directory — commit raises ToolError."""
    nogit = tempfile.mkdtemp()
    try:

        async def go():
            server = build_server(StoreProvider(Path(nogit), "test"))
            async with Client(server) as c:
                r = await c.call_tool(
                    "commit",
                    {"ids": ["0001"], "message": "x"},
                    raise_on_error=False,
                )
                return r

        r = asyncio.run(go())
        assert r.is_error is True
        error_str = str(
            r.structured_content if hasattr(r, "structured_content") and r.structured_content else r
        )
        assert "storage is not under git" in error_str
    finally:
        shutil.rmtree(nogit, ignore_errors=True)
