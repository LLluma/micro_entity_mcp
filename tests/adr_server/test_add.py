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
                    "id": "ADR-0007",
                    "title": "Some decision",
                    "body": "prose",
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["id"] == "ADR-0007"
    assert data["attributes"]["title"] == "Some decision"
    assert data["attributes"]["status"] == "Proposed"
    assert data["body"] == "prose"


def test_add_duplicate_id_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0008",
                    "title": "First",
                    "body": "b",
                },
            )
            result = await c.call_tool(
                "create",
                {
                    "id": "ADR-0008",
                    "title": "Second",
                    "body": "b",
                },
                raise_on_error=False,
            )
        assert result.is_error is True

    asyncio.run(go())


def test_add_invalid_status_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {
                    "id": "ADR-0009",
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
                    "id": "ADR-0011",
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
                    "id": "ADR-0012",
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
                    "id": "ADR-0010",
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "Accepted"},
                },
            )

    r = asyncio.run(go())
    data = (_tc(dict, r.structured_content))["item"]
    assert data["attributes"]["status"] == "Accepted"
