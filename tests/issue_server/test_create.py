import asyncio
from pathlib import Path
from typing import cast as _tc

from mcp.types import TextContent

from tests.issue_server.conftest import _client


def test_create_returns_entity_with_id_status_title_commit(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "Bug in parser",
                    "body": "traceback on line 42",
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["id"] == "ISSUE-0001"
    assert data["attributes"]["status"] == "open"
    assert data["attributes"]["title"] == "Bug in parser"
    full = _tc(dict, r.structured_content)
    assert isinstance(full["commit"], str)
    assert len(full["commit"]) > 0


def test_create_assigns_sequential_ids(tmp_path: Path) -> None:
    """Server-assigned ids are sequential."""

    async def go():
        async with _client(tmp_path) as c:
            first = await c.call_tool("create", {"title": "First", "body": "b"})
            second = await c.call_tool("create", {"title": "Second", "body": "b"})
        d1 = _tc(dict, first.structured_content)["item"]
        d2 = _tc(dict, second.structured_content)["item"]
        assert d1["id"] == "ISSUE-0001"
        assert d2["id"] == "ISSUE-0002"

    asyncio.run(go())


def test_create_with_closed_status_accepted(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "old issue",
                    "body": "closed by intent",
                    "attributes": {"status": "closed"},
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["attributes"]["status"] == "closed"


def test_create_with_bogus_status_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "bogus"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_create_rejects_reserved_id_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {"id": "x"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_create_explicit_status_param(tmp_path: Path) -> None:
    """create(..., status='closed') produces that status."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"title": "t", "body": "b", "status": "closed"})

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["attributes"]["status"] == "closed"


def test_create_explicit_status_param_invalid(tmp_path: Path) -> None:
    """create(..., status='bogus') raises ToolError with 'invalid value'."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"title": "t", "body": "b", "status": "bogus"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True
    msg = _tc(TextContent, r.content[0]).text if r.content else ""
    assert "invalid value" in msg


def test_create_status_param_vs_attributes_precedence(tmp_path: Path) -> None:
    """Explicit status param overrides attributes={'status': 'open'}."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "wontfix"},
                    "status": "closed",
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["attributes"]["status"] == "closed"
