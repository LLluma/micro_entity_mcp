# pyright: reportOptionalSubscript=false
"""Verify _normalize_todo_id wiring through server tools."""

import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client


def test_get_by_short_id(tmp_path: "Path") -> None:
    """Create → id is "0001". get("1") should return the same entity."""

    async def go() -> dict:
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "test item"})
            item = (_tc(dict, created.structured_content))["item"]
            assert item["id"] == "0001"
            result = await c.call_tool("get", {"id": "1"})
            returned = (_tc(dict, result.structured_content))["item"]
            assert returned["id"] == "0001"
            return returned

    asyncio.run(go())


def test_update_by_short_id(tmp_path: "Path") -> None:
    """Create → update("1") with status change returns entity with canonical id."""

    async def go() -> dict:
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "test item"})
            result = await c.call_tool("update", {"id": "1", "status": "done"})
            returned = (_tc(dict, result.structured_content))["item"]
            assert returned["id"] == "0001"
            assert returned["attributes"]["status"] == "done"
            return returned

    asyncio.run(go())


def test_get_nonexistent_numeric_id(tmp_path: "Path") -> None:
    """get("7") on empty store raises with message containing '0007'."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "7"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "not found: 0007" in str(exc_info.value)


def test_get_does_not_contain_raw_id(tmp_path: "Path") -> None:
    """The raw un-normalized id must NOT appear in the error message."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "7"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    # Confirm the canonical form, not raw, is in the message
    assert "not found: 7" not in str(exc_info.value)


def test_delete_by_short_id(tmp_path: "Path") -> None:
    """Create → delete("1") removes the entity. Subsequent get("1") fails."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "to remove"})
            result = await c.call_tool("delete", {"id": "1"})
            assert (_tc(dict, result.structured_content))["id"] == "0001"
            return await c.call_tool("get", {"id": "1"})

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())
    assert "not found" in str(exc_info.value)
