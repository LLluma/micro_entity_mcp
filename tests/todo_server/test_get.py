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
            entity_id = created.data["item"]["id"]
            result = await c.call_tool("get", {"id": entity_id})
            return result.data

    data = asyncio.run(go())
    assert data["item"]["id"] == "0001"
    assert data["item"]["body"] == "get test item"


def test_get_missing_id_raises_tool_error(tmp_path: Path) -> None:
    """Calling get with a non-existent id raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "9999"})

    with pytest.raises(ToolError):
        asyncio.run(go())


def test_get_missing_id_message_is_normalized(tmp_path: Path) -> None:
    """The ToolError message for a missing id is exactly 'not found: <id>'."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "missing-42"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())

    assert str(exc_info.value) == "not found: missing-42"
