import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client


def test_is_complete_all_done(tmp_path: Path) -> None:
    """Create an item, update to done → is_complete returns True."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "done item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data["complete"] is True


def test_is_complete_any_todo(tmp_path: Path) -> None:
    """Default create gives status todo → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "todo item", "attributes": {}})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data["complete"] is False


def test_is_complete_any_in_progress(tmp_path: Path) -> None:
    """Item with status in-progress → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "wip item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "in-progress"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data["complete"] is False


def test_is_complete_any_blocked(tmp_path: Path) -> None:
    """Item with status blocked → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "blocked item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "blocked"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data["complete"] is False


def test_is_complete_empty_partition(tmp_path: Path) -> None:
    """No items at all → vacuous True."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data["complete"] is True
