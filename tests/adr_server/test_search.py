import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.adr_server.conftest import _client


def test_search_matches_body_substring(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "T",
                    "body": "The quick brown fox",
                },
            )
            return await c.call_tool("search", {"text": "quick"})

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["items"]) == 1
    assert (_tc(dict, r.structured_content))["items"][0]["id"] == "ADR-0001"


def test_search_matches_tag_value(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "T2",
                    "body": "nothing",
                    "attributes": {"tags": ["durable", "schema"]},
                },
            )
            return await c.call_tool("search", {"text": "durable"})

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["items"]) == 1
    assert (_tc(dict, r.structured_content))["items"][0]["id"] == "ADR-0001"


def test_search_case_insensitive(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "Case test",
                    "body": "The Quick Brown Fox",
                },
            )
            return await c.call_tool("search", {"text": "QUICK"})

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["items"]) == 1
    assert (_tc(dict, r.structured_content))["items"][0]["id"] == "ADR-0001"


def test_search_no_match_returns_empty(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "T",
                    "body": "nothing here",
                },
            )
            return await c.call_tool("search", {"text": "zzzznomatch"})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["items"] == []


def test_search_matches_title_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "Persistence Layer",
                    "body": "x",
                },
            )
            return await c.call_tool("search", {"text": "persistence"})

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["items"]) == 1
    assert (_tc(dict, r.structured_content))["items"][0]["id"] == "ADR-0001"


def test_search_default_omits_body(tmp_path: Path) -> None:
    """By default, search items must NOT contain a 'body' key."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "Body omission test",
                    "body": "The quick brown fox jumps over the lazy dog",
                },
            )
            return await c.call_tool("search", {"text": "quick"})

    r = asyncio.run(go())
    items = _tc(dict, r.structured_content)["items"]
    assert len(items) == 1
    item = items[0]
    # Must NOT have body key when include_body is not set
    assert "body" not in item
    # But id and attributes must still be present
    assert "id" in item
    assert item["id"] == "ADR-0001"
    assert "title" in item.get("attributes", {})


def test_search_include_body_returns_full_body(tmp_path: Path) -> None:
    """With include_body=True, search items MUST contain a 'body' key."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "Body inclusion test",
                    "body": "The exact body text we expect back",
                },
            )
            return await c.call_tool(
                "search",
                {"text": "exact", "include_body": True},
            )

    r = asyncio.run(go())
    items = _tc(dict, r.structured_content)["items"]
    assert len(items) == 1
    item = items[0]
    assert "body" in item
    assert item["body"] == "The exact body text we expect back"
