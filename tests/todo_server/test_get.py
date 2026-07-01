import asyncio
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client


def test_get_returns_created_entity(tmp_path: Path) -> None:
    """Create an item, then get by id: id and body must match."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "get test item", "attributes": {}})
            entity_id = created.data["id"]
            result = await c.call_tool("get", {"id": entity_id})
            return result.data

    data = asyncio.run(go())
    assert data["id"] == "0001"
    assert data["body"] == "get test item"


def test_get_missing_id_raises_tool_error(tmp_path: Path) -> None:
    """Calling get with a non-existent id raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "9999"})

    with pytest.raises(ToolError):
        asyncio.run(go())
