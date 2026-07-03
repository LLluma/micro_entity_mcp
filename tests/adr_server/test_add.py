import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest

from tests.adr_server.conftest import _client


def test_add_returns_entity_dict(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "Some decision",
                    "body": "prose",
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["id"] == "ADR-0001"
    assert data["attributes"]["title"] == "Some decision"
    assert data["attributes"]["status"] == "Proposed"
    assert data["body"] == "prose"


def test_add_assigns_sequential_ids(tmp_path: Path) -> None:
    """Server-assigned ids are sequential: first call → ADR-0001, second → ADR-0002."""

    async def go():
        async with _client(tmp_path) as c:
            first = await c.call_tool(
                "create",
                {
                    "title": "First",
                    "body": "b",
                },
            )
            second = await c.call_tool(
                "create",
                {
                    "title": "Second",
                    "body": "b",
                },
            )
        assert isinstance(first.structured_content, dict)
        assert isinstance(second.structured_content, dict)
        d1 = _tc(dict, first.structured_content)["item"]
        d2 = _tc(dict, second.structured_content)["item"]
        assert d1["id"] == "ADR-0001"
        assert d2["id"] == "ADR-0002"

    asyncio.run(go())


def test_add_invalid_status_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "Bogus"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_add_rejects_reserved_created_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {"created": "x"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


@pytest.mark.parametrize("reserved_key", ["updated", "id"])
def test_add_rejects_other_reserved_attributes(tmp_path: Path, reserved_key: str) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {reserved_key: "x"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_add_custom_valid_status_honored(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "Accepted"},
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["attributes"]["status"] == "Accepted"


def test_add_explicit_status_param(tmp_path: Path) -> None:
    """create(..., status='Accepted') produces that status."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"title": "t", "body": "b", "status": "Accepted"},
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["attributes"]["status"] == "Accepted"


def test_add_explicit_status_param_invalid(tmp_path: Path) -> None:
    """create(..., status='Bogus') raises ToolError with 'invalid value'."""
    from mcp.types import TextContent

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"title": "t", "body": "b", "status": "Bogus"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True
    msg = _tc(TextContent, r.content[0]).text if r.content else ""
    assert "invalid value" in msg


def test_add_status_param_vs_attributes_precedence(tmp_path: Path) -> None:
    """Explicit status param overrides attributes={'status': 'Proposed'}."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "Superseded"},
                    "status": "Accepted",
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["attributes"]["status"] == "Accepted"
