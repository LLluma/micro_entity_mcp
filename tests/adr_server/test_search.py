import asyncio
from pathlib import Path

from tests.adr_server.conftest import _client


def test_search_matches_body_substring(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "The quick brown fox",
                },
            )
            return await c.call_tool("search", {"text": "quick"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0007"


def test_search_matches_tag_value(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0008",
                    "title": "T2",
                    "body": "nothing",
                    "attributes": {"tags": ["durable", "schema"]},
                },
            )
            return await c.call_tool("search", {"text": "durable"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0008"


def test_search_case_insensitive(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0009",
                    "title": "Case test",
                    "body": "The Quick Brown Fox",
                },
            )
            return await c.call_tool("search", {"text": "QUICK"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0009"


def test_search_no_match_returns_empty(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0010",
                    "title": "T",
                    "body": "nothing here",
                },
            )
            return await c.call_tool("search", {"text": "zzzznomatch"})

    r = asyncio.run(go())
    assert r.data["items"] == []


def test_search_matches_title_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0009",
                    "title": "Persistence Layer",
                    "body": "x",
                },
            )
            return await c.call_tool("search", {"text": "persistence"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0009"
