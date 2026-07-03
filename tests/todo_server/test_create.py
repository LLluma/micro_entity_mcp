# pyright: reportOptionalSubscript=false, reportOperatorIssue=false, reportOptionalMemberAccess=false
import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp.exceptions import ToolError
from mcp.types import TextContent

from tests.todo_server.conftest import _client


def test_create_defaults_status_and_order(tmp_path: Path) -> None:
    """Create with body: status==\"todo\", order==1, fresh id, body echoed."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "buy milk", "attributes": {}})

    r = asyncio.run(go())
    assert set(r.structured_content.keys()) == {"item", "commit"}
    item = (_tc(dict, r.structured_content))["item"]
    assert item["attributes"]["status"] == "todo"
    assert item["attributes"]["order"] == 1
    assert item["body"] == "buy milk"


def test_create_order_increments(tmp_path: Path) -> None:
    """Creating twice: second item gets order==2 and larger id."""

    async def go():
        async with _client(tmp_path) as c:
            first = await c.call_tool("create", {"body": "first", "attributes": {}})
            second = await c.call_tool("create", {"body": "second", "attributes": {}})
        return first.structured_content, second.structured_content

    first, second = asyncio.run(go())
    assert set(first.keys()) == {"item", "commit"}
    assert set(second.keys()) == {"item", "commit"}
    assert first["item"]["attributes"]["order"] == 1
    assert second["item"]["attributes"]["order"] == 2
    assert second["item"]["id"] > first["item"]["id"]


def test_create_honours_custom_status(tmp_path: Path) -> None:
    """Passing attributes={\"status\": \"in-progress\"} is honored."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "wip item", "attributes": {"status": "in-progress"}},
            )

    r = asyncio.run(go())
    assert set(r.structured_content.keys()) == {"item", "commit"}
    assert (_tc(dict, r.structured_content))["item"]["attributes"]["status"] == "in-progress"


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


def test_create_explicit_status_param(tmp_path: Path) -> None:
    """create(..., status='in-progress') produces that status."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "x", "status": "in-progress"})

    r = asyncio.run(go())
    item = (_tc(dict, r.structured_content))["item"]
    assert item["attributes"]["status"] == "in-progress"


def test_create_explicit_status_param_invalid(tmp_path: Path) -> None:
    """create(..., status='bogus') raises ToolError with 'invalid value'."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create", {"body": "x", "status": "bogus"}, raise_on_error=False
            )

    r = asyncio.run(go())
    assert r.is_error is True
    msg = _tc(TextContent, r.content[0]).text if r.content else ""
    assert "invalid value" in msg


def test_create_status_param_vs_attributes_precedence(tmp_path: Path) -> None:
    """Explicit status param overrides attributes={'status': 'A'}."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "x", "attributes": {"status": "done"}, "status": "blocked"},
            )

    r = asyncio.run(go())
    item = (_tc(dict, r.structured_content))["item"]
    assert item["attributes"]["status"] == "blocked"


def test_create_returns_wrapped_dict(tmp_path: Path) -> None:
    """create wraps entity in {"item": <entity-dict>}; no top-level id/body/attributes."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "x", "attributes": {}})

    r = asyncio.run(go())
    data = r.structured_content
    assert data is not None
    # Top-level keys: "item" plus additive "commit"
    assert set(data.keys()) == {"item", "commit"}
    # Top-level does NOT leak entity fields
    assert "id" not in data
    assert "body" not in data
    assert "attributes" not in data
    item = data["item"]
    # Entity dict contains expected fields
    assert "id" in item
    assert "body" in item
    assert "attributes" in item
    assert item["attributes"]["status"] == "todo"
    assert "order" in item["attributes"]
