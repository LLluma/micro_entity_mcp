import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.todo_server.conftest import _client


def test_is_complete_empty_partition_returns_done_total(tmp_path: Path) -> None:
    """No items → complete=True, done=0, total=0."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    sc = _tc(dict, r.structured_content)
    assert sc["complete"] is True
    assert sc["done"] == 0 and sc["total"] == 0


def test_is_complete_partial_done(tmp_path: Path) -> None:
    """2 todos, 1 done → complete=False, done=1, total=2."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "a", "attributes": {}})
            await c.call_tool("create", {"body": "b", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    sc = _tc(dict, r.structured_content)
    assert sc["complete"] is False
    assert sc["done"] == 1 and sc["total"] == 2


def test_is_complete_all_done_returns_done_total(tmp_path: Path) -> None:
    """2 todos both done → complete=True, done=2, total=2 (complete == done == total)."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "a", "attributes": {}})
            await c.call_tool("create", {"body": "b", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            await c.call_tool("update", {"id": "0002", "status": "done"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    sc = _tc(dict, r.structured_content)
    assert sc["complete"] is True
    assert sc["done"] == 2 and sc["total"] == 2
    assert sc["complete"] is (sc["done"] == sc["total"])


def test_is_complete_all_done(tmp_path: Path) -> None:
    """Create an item, update to done → is_complete returns True."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "done item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["complete"] is True


def test_is_complete_any_todo(tmp_path: Path) -> None:
    """Default create gives status todo → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "todo item", "attributes": {}})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["complete"] is False


def test_is_complete_any_in_progress(tmp_path: Path) -> None:
    """Item with status in-progress → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "wip item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "in-progress"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["complete"] is False


def test_is_complete_any_blocked(tmp_path: Path) -> None:
    """Item with status blocked → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "blocked item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "blocked"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["complete"] is False


def test_is_complete_empty_partition(tmp_path: Path) -> None:
    """No items at all → vacuous True."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["complete"] is True
