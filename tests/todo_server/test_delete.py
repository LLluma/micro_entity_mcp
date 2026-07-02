# pyright: reportOptionalSubscript=false, reportOperatorIssue=false, reportOptionalMemberAccess=false
import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client


def test_delete_removes_item(tmp_path: Path) -> None:
    """Create an item, delete it (assert returned {"ok": True, "id": <id>}),
    then get on that id raises ToolError (item is gone)."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "deleteme", "attributes": {}})
            item_id = (_tc(dict, created.structured_content))["item"]["id"]
            deleted = await c.call_tool("delete", {"id": item_id})
            return deleted.structured_content, item_id

    deleted_data, item_id = asyncio.run(go())
    assert "ok" in deleted_data
    assert "id" in deleted_data
    assert "commit" in deleted_data
    assert deleted_data["ok"] is True
    assert deleted_data["id"] == item_id

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


def test_delete_missing_id_message_is_normalized(tmp_path: Path) -> None:
    """The ToolError message for a missing id is exactly 'not found: <id>'."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("delete", {"id": "missing-42"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())

    assert str(exc_info.value) == "not found: missing-42"
