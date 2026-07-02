import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client


def test_clear_with_n_todos_returns_count(tmp_path: Path) -> None:
    """Seed N todos, call clear, assert {"ok": True, "cleared": N} and
    the list is now empty."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "first", "attributes": {}})
            await c.call_tool("create", {"body": "second", "attributes": {}})
            await c.call_tool("create", {"body": "third", "attributes": {}})
            cleared = await c.call_tool("clear", {})
            listed = await c.call_tool("list", {})
            return cleared.data, listed.data["items"]

    cleared_data, items = asyncio.run(go())
    assert cleared_data == {"ok": True, "cleared": 3}
    assert items == []


def test_clear_empty_partition_returns_zero(tmp_path: Path) -> None:
    """Clear a store with zero todos — assert cleared == 0."""

    async def go():
        async with _client(tmp_path) as c:
            cleared = await c.call_tool("clear", {})
            return cleared.data

    cleared_data = asyncio.run(go())
    assert cleared_data == {"ok": True, "cleared": 0}
