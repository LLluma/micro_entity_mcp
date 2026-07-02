"""Verify that adr tools advertise a non-null outputSchema."""

import asyncio
from pathlib import Path

from tests.adr_server.conftest import _client


def test_create_output_schema(tmp_path: Path) -> None:
    """create's outputSchema has keys: item, commit."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        return {t.name: t for t in tools}

    s = asyncio.run(go())
    schema = s["create"].outputSchema
    assert schema is not None
    props = schema.get("properties", {})
    assert "item" in props
    assert "commit" in props


def test_supersede_output_schema(tmp_path: Path) -> None:
    """supersede's outputSchema has keys: superseded, superseding, commit."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        return {t.name: t for t in tools}

    s = asyncio.run(go())
    schema = s["supersede"].outputSchema
    assert schema is not None
    props = schema.get("properties", {})
    assert "superseded" in props
    assert "superseding" in props
    assert "commit" in props


def test_list_output_schema(tmp_path: Path) -> None:
    """list's outputSchema has keys: items, errors."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        return {t.name: t for t in tools}

    s = asyncio.run(go())
    schema = s["list"].outputSchema
    assert schema is not None
    props = schema.get("properties", {})
    assert "items" in props
    assert "errors" in props
