"""Verify that every todo tool advertises a non-null outputSchema."""

import asyncio

from tests.todo_server.conftest import _client


def test_create_output_schema(tmp_path) -> None:
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


def test_list_output_schema(tmp_path) -> None:
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


def test_diff_output_schema(tmp_path) -> None:
    """diff's outputSchema has key: diff."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        return {t.name: t for t in tools}

    s = asyncio.run(go())
    schema = s["diff"].outputSchema
    assert schema is not None
    props = schema.get("properties", {})
    assert "diff" in props


def test_health_output_schema(tmp_path) -> None:
    """health's outputSchema has keys: base, segment, dir."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        return {t.name: t for t in tools}

    s = asyncio.run(go())
    schema = s["health"].outputSchema
    assert schema is not None
    props = schema.get("properties", {})
    assert "base" in props
    assert "segment" in props
    assert "dir" in props
