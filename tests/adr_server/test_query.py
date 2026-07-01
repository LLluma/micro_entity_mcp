import asyncio
from pathlib import Path

from tests.adr_server.conftest import _client


def test_query_filter_by_tags(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "b",
                    "attributes": {"tags": ["durable"]},
                },
            )
            await c.call_tool(
                "add",
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
                "add",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "add",
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
                "add",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "T2", "body": "b2"},
            )
            return await c.call_tool("query", {})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 2


def test_query_no_match_empty(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            return await c.call_tool(
                "query",
                {"criteria": {"tags": ["nonexistent"]}},
            )

    r = asyncio.run(go())
    assert r.data["items"] == []
