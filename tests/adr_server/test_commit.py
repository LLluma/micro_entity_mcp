"""Tests for the ADR server `commit` tool."""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import cast as _tc

from fastmcp import Client

from micro_entity import vcs
from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client


def test_commit_pending_change(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            # Create ADR via tool (auto-commits)
            await c.call_tool(
                "create",
                {"title": "T", "body": "B"},
            )
            # Dirty the file on disk
            p = tmp_path / "seg" / "ADR-0001.md"
            p.write_text(p.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
            # Commit the pending change
            result = await c.call_tool(
                "commit",
                {"ids": ["ADR-0001"], "message": "checkpoint"},
            )
        return result

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert data["ok"] is True
    assert data["commit"] is not None
    assert data["ids"] == ["ADR-0001"]

    root = vcs.find_repo_root(tmp_path)
    p = tmp_path / "seg" / "ADR-0001.md"
    newest = vcs.file_log(root, p, limit=5)[0]
    assert newest["message"] == "checkpoint"


def test_commit_no_pending_change(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            # Create ADR via tool (auto-commits) — clean state
            await c.call_tool(
                "create",
                {"title": "T", "body": "B"},
            )
            # Commit with no dirty files
            result = await c.call_tool(
                "commit",
                {"ids": ["ADR-0001"], "message": "noop"},
            )
        return result

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    assert data["ok"] is True
    assert data["commit"] is None
    assert data["ids"] == ["ADR-0001"]


def test_commit_non_git_store_raises_tool_error() -> None:
    nogit = tempfile.mkdtemp()
    try:
        provider = StoreProvider(Path(nogit), "seg")

        async def go():
            async with Client(build_server(provider)) as c:
                return await c.call_tool(
                    "commit",
                    {"ids": ["ADR-0001"], "message": "will-not-work"},
                    raise_on_error=False,
                )

        r = asyncio.run(go())
        assert r.is_error is True
    finally:
        shutil.rmtree(nogit, ignore_errors=True)
