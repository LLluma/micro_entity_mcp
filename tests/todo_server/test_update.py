import asyncio
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client


def test_update_status_transition_persists(tmp_path: Path) -> None:
    """Create an item, update its status to \"in-progress\", assert change."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "update status test", "attributes": {}},
            )
            item_id = created.data["item"]["id"]
            updated = await c.call_tool("update", {"id": item_id, "status": "in-progress"})
            return created.data["item"], updated.data

    created, updated = asyncio.run(go())
    assert created["attributes"]["status"] == "todo"
    assert updated["attributes"]["status"] == "in-progress"


def test_update_status_invalid_raises(tmp_path: Path) -> None:
    """Invalid status string raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "bad status", "attributes": {}},
            )
            return await c.call_tool(
                "update", {"id": created.data["item"]["id"], "status": "bogus"}
            )

    with pytest.raises(ToolError):
        asyncio.run(go())


def test_update_order_change_persists(tmp_path: Path) -> None:
    """Update order to 5, assert returned and get'd order == 5."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "order test", "attributes": {}},
            )
            item_id = created.data["item"]["id"]
            updated = await c.call_tool("update", {"id": item_id, "order": 5})
            fetched = await c.call_tool("get", {"id": item_id})
            return updated.data, fetched.data

    updated, fetched = asyncio.run(go())
    assert updated["attributes"]["order"] == 5
    assert fetched["attributes"]["order"] == 5


def test_update_missing_id_raises(tmp_path: Path) -> None:
    """Update a non-existent id raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("update", {"id": "9999", "status": "done"})

    with pytest.raises(ToolError):
        asyncio.run(go())


def test_update_unspecified_fields_unchanged(tmp_path: Path) -> None:
    """Update only order body and status remain unchanged in returned/get'd entity."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "original body", "attributes": {"status": "done"}},
            )
            item_id = created.data["item"]["id"]
            original_body = created.data["item"]["body"]
            original_status = created.data["item"]["attributes"]["status"]
            updated = await c.call_tool("update", {"id": item_id, "order": 99})
            fetched = await c.call_tool("get", {"id": item_id})
            return updated.data, fetched.data, original_body, original_status

    updated, fetched, original_body, original_status = asyncio.run(go())

    # Changed field
    assert updated["attributes"]["order"] == 99
    assert fetched["attributes"]["order"] == 99

    # Unchanged fields in both update return and get'd entity
    assert updated["body"] == original_body
    assert updated["attributes"]["status"] == original_status
    assert fetched["body"] == original_body
    assert fetched["attributes"]["status"] == original_status
