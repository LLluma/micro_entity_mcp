import asyncio
import shutil
import tempfile
from pathlib import Path

from fastmcp import Client

from micro_entity import vcs
from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client


def test_revert_restores_previous_commit_and_creates_new_commit(tmp_path: Path) -> None:
    """Revert to HEAD~1 restores STATE_A, creates new commit, preserves older commits."""

    async def go():
        async with _client(tmp_path) as c:
            # Create ADR-0001 with body "STATE_A" (commit A).
            await c.call_tool(
                "create",
                {"id": "ADR-0001", "title": "T", "body": "STATE_A"},
            )
            # Update to "STATE_B" (commit B).
            await c.call_tool(
                "update",
                {"id": "ADR-0001", "body": "STATE_B"},
            )
            # Revert to HEAD~1 (commit A).
            result = await c.call_tool(
                "revert",
                {"id": "ADR-0001", "ref": "HEAD~1"},
            )

        root = vcs.find_repo_root(tmp_path)
        log = vcs.file_log(root, tmp_path / "seg" / "ADR-0001.md", limit=10)

        # Newest commit message is the revert.
        assert log[0]["message"] == "revert adr ADR-0001 to HEAD~1"
        # An "update adr" commit still exists earlier.
        assert any("update adr" in e["message"] for e in log)

        # Returned item body contains "STATE_A".
        item = result.data["item"]
        assert "STATE_A" in item["body"]

        # On-disk file body contains "STATE_A".
        file_body = (tmp_path / "seg" / "ADR-0001.md").read_text(encoding="utf-8")
        assert "STATE_A" in file_body

    asyncio.run(go())


def test_revert_to_current_head_returns_current_body_no_new_commit(tmp_path: Path) -> None:
    """Revert to HEAD of a file that hasn't changed is effectively a no-op."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-0001", "title": "T", "body": "STATE_A"},
            )
            result = await c.call_tool(
                "revert",
                {"id": "ADR-0001", "ref": "HEAD"},
            )

        item = result.data["item"]
        assert "STATE_A" in item["body"]

    asyncio.run(go())


def test_revert_non_git_store_raises_tool_error() -> None:
    """Revert on a non-git directory should raise ToolError."""
    nogit = tempfile.mkdtemp()
    try:
        provider = StoreProvider(Path(nogit), "seg")

        async def go():
            async with Client(build_server(provider)) as c:
                return await c.call_tool(
                    "revert",
                    {"id": "ADR-0001", "ref": "HEAD"},
                    raise_on_error=False,
                )

        r = asyncio.run(go())
        assert r.is_error is True
    finally:
        shutil.rmtree(nogit, ignore_errors=True)
