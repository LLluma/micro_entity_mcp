import asyncio
from pathlib import Path

from tests.adr_server.conftest import _client


def test_query_filter_by_tags(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "b",
                    "attributes": {"tags": ["durable"]},
                },
            )
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0008",
                    "title": "T",
                    "body": "b",
                    "attributes": {"tags": ["ephemeral"]},
                },
            )
            return await c.call_tool(
                "query",
                {"criteria": {"tags": ["durable"]}},
            )

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0007"


def test_query_filter_by_status(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "create",
                {"id": "ADR-0008", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "update",
                {"id": "ADR-0007", "status": "Accepted"},
            )
            return await c.call_tool(
                "query",
                {"criteria": {"status": ["Accepted"]}},
            )

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0007"


def test_query_empty_returns_all(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "create",
                {"id": "ADR-0008", "title": "T2", "body": "b2"},
            )
            return await c.call_tool("query", {})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 2


def test_query_no_match_empty(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            return await c.call_tool(
                "query",
                {"criteria": {"tags": ["nonexistent"]}},
            )

    r = asyncio.run(go())
    assert r.data["items"] == []


def test_query_docstring_substrings(tmp_path: Path) -> None:
    """Assert the query tool's docstring documents criteria shape, semantics,
    and type-strict caveat."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "query")
            return tool.description

    desc = str(asyncio.run(go()))
    assert "{key: [values]}" in desc
    assert "within-key OR, across-key AND" in desc
    assert "type-strict" in desc
