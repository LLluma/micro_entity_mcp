import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client


def test_next_returns_lowest_order_actionable(tmp_path: Path) -> None:
    """Two items with orders 1 and 2, both status=todo: next returns order-1 item."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "item one", "attributes": {"status": "todo"}},
            )
            await c.call_tool("create", {"body": "item two", "attributes": {"status": "todo"}})
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data["attributes"]["order"] == 1
    assert r.data["body"] == "item one"


def test_next_skips_done_and_blocked(tmp_path: Path) -> None:
    """Item 1=done, item 2=blocked, item 3=todo: next returns item 3."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "done item", "attributes": {"status": "todo"}})
            await c.call_tool("create", {"body": "blocked item", "attributes": {"status": "todo"}})
            await c.call_tool("create", {"body": "todo item", "attributes": {"status": "todo"}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            await c.call_tool("update", {"id": "0002", "status": "blocked"})
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data["attributes"]["order"] == 3
    assert r.data["id"] == "0003"


def test_next_empty_partition_returns_none(tmp_path: Path) -> None:
    """No actionable entities → data is None."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data is None


def test_next_all_done_returns_none(tmp_path: Path) -> None:
    """One item, updated to done → next returns None."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "done item", "attributes": {"status": "todo"}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data is None
