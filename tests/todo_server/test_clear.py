import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client


def test_clear_empty_partition(tmp_path: Path) -> None:
    """Create two items, call clear (assert returned {"cleared": True}),
    then list returns items == []."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "first", "attributes": {}})
            await c.call_tool("create", {"body": "second", "attributes": {}})
            cleared = await c.call_tool("clear", {})
            listed = await c.call_tool("list", {})
            return cleared.data, listed.data["items"]

    cleared_data, items = asyncio.run(go())
    assert cleared_data == {"cleared": True}
    assert items == []
