import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.issue_server.conftest import _client


def test_update_closes_issue(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "b"})
            await c.call_tool("update", {"id": "ISSUE-0001", "status": "closed"})
            result = await c.call_tool("get", {"id": "ISSUE-0001"})
        data = (_tc(dict, result.structured_content))["item"]
        assert data["attributes"]["status"] == "closed"

    asyncio.run(go())


def test_update_wontfix_issue(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "b"})
            await c.call_tool("update", {"id": "ISSUE-0001", "status": "wontfix"})
            result = await c.call_tool("get", {"id": "ISSUE-0001"})
        data = (_tc(dict, result.structured_content))["item"]
        assert data["attributes"]["status"] == "wontfix"

    asyncio.run(go())


def test_update_bogus_status_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "b"})
            return await c.call_tool(
                "update",
                {"id": "ISSUE-0001", "status": "bogus"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True
