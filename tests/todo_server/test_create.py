import asyncio
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client


def test_create_defaults_status_and_order(tmp_path: Path) -> None:
    """Create with body: status==\"todo\", order==1, fresh id, body echoed."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "buy milk", "attributes": {}})

    r = asyncio.run(go())
    data = r.data
    assert data["attributes"]["status"] == "todo"
    assert data["attributes"]["order"] == 1
    assert data["body"] == "buy milk"


def test_create_order_increments(tmp_path: Path) -> None:
    """Creating twice: second item gets order==2 and larger id."""

    async def go():
        async with _client(tmp_path) as c:
            first = await c.call_tool("create", {"body": "first", "attributes": {}})
            second = await c.call_tool("create", {"body": "second", "attributes": {}})
        return first.data, second.data

    first, second = asyncio.run(go())
    assert first["attributes"]["order"] == 1
    assert second["attributes"]["order"] == 2
    assert second["id"] > first["id"]


def test_create_honours_custom_status(tmp_path: Path) -> None:
    """Passing attributes={\"status\": \"in-progress\"} is honored."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "wip item", "attributes": {"status": "in-progress"}},
            )

    r = asyncio.run(go())
    assert r.data["attributes"]["status"] == "in-progress"


def test_create_rejects_bogus_status(tmp_path: Path) -> None:
    """Passing attributes={\"status\": \"bogus\"} raises a tool error."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "bad status", "attributes": {"status": "bogus"}},
            )

    with pytest.raises(ToolError):
        asyncio.run(go())


def test_create_rejects_reserved_created_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "bad", "attributes": {"created": "x"}},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


@pytest.mark.parametrize("reserved_key", ["updated", "id"])
def test_create_rejects_other_reserved_attributes(tmp_path: Path, reserved_key: str) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "bad", "attributes": {reserved_key: "x"}},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True
