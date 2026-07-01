import asyncio
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client


def test_delete_removes_item(tmp_path: Path) -> None:
    """Create an item, delete it (assert returned {"deleted": <id>}),
    then get on that id raises ToolError (item is gone)."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "deleteme", "attributes": {}})
            item_id = created.data["id"]
            deleted = await c.call_tool("delete", {"id": item_id})
            return deleted.data, item_id

    deleted_data, item_id = asyncio.run(go())
    assert deleted_data == {"deleted": item_id}

    # After deletion, get should raise ToolError
    async def get_after():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": item_id})

    with pytest.raises(ToolError):
        asyncio.run(get_after())


def test_delete_missing_id_raises_tool_error(tmp_path: Path) -> None:
    """Deleting a non-existent id raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("delete", {"id": "9999"})

    with pytest.raises(ToolError):
        asyncio.run(go())
