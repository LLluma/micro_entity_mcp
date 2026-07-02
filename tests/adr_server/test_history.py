import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import cast as _tc

from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client


def test_history_returns_commits_newest_first(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "T", "body": "B"},
            )
            await c.call_tool(
                "update",
                {"id": "ADR-0001", "body": "B1"},
            )
            await c.call_tool(
                "update",
                {"id": "ADR-0001", "body": "B2"},
            )
            return await c.call_tool("history", {"id": "ADR-0001"})

    r = asyncio.run(go())
    commits = (_tc(dict, r.structured_content))["commits"]
    assert len(commits) == 3, f"expected 3 commits, got {len(commits)}"
    # newest-first: message contains the update for ADR-0001
    assert "update adr ADR-0001" in commits[0]["message"]
    for c in commits:
        assert c["sha"], "sha must be non-empty"
        assert c["date"], "date must be non-empty"
        assert c["message"], "message must be non-empty"


def test_history_with_limit_returns_exact_count(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "T", "body": "B"},
            )
            await c.call_tool("update", {"id": "ADR-0001", "body": "X"})
            return await c.call_tool("history", {"id": "ADR-0001", "limit": 1})

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["commits"]) == 1


def test_history_non_git_store_raises_tool_error() -> None:
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
