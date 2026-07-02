"""Tests for the todo `search` tool and `_entity_matches_text` helper."""

import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.todo_server.conftest import _client


def test_search_matches_body_substring(tmp_path: Path) -> None:
    """Create a todo whose body contains "quick"; search text="quick"
    returns exactly that one item, matched by id."""

    async def go():
        async with _client(tmp_path) as c:
            resp = await c.call_tool("create", {"body": "The quick brown fox"})
            created_id = _tc(dict, resp.structured_content)["item"]["id"]
            result = await c.call_tool("search", {"text": "quick"})
            content = _tc(dict, result.structured_content)
            items = content["items"]
            return items, created_id

    items, created_id = asyncio.run(go())
    assert len(items) == 1
    assert items[0]["id"] == created_id


def test_search_case_insensitive(tmp_path: Path) -> None:
    """Body 'The Quick Brown Fox'; search text='QUICK' matches."""

    async def go():
        async with _client(tmp_path) as c:
            resp = await c.call_tool("create", {"body": "The Quick Brown Fox"})
            created_id = _tc(dict, resp.structured_content)["item"]["id"]
            result = await c.call_tool("search", {"text": "QUICK"})
            content = _tc(dict, result.structured_content)
            items = content["items"]
            return items, created_id

    items, created_id = asyncio.run(go())
    assert len(items) == 1
    assert items[0]["id"] == created_id


def test_search_matches_attribute_value(tmp_path: Path) -> None:
    """Create a todo with an attribute containing a distinctive word;
    search that word returns the item."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "some task", "attributes": {"team": "pumas"}},
            )
            result = await c.call_tool("search", {"text": "pumas"})
            content = _tc(dict, result.structured_content)
            items = content["items"]
            return items

    items = asyncio.run(go())
    assert len(items) == 1
    assert items[0]["attributes"]["team"] == "pumas"


def test_search_non_matching_returns_empty(tmp_path: Path) -> None:
    """Search for text absent from all entities returns empty items list."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "hello world"})
            result = await c.call_tool("search", {"text": "zzzznotfound"})
            content = _tc(dict, result.structured_content)
            items = content["items"]
            return items

    items = asyncio.run(go())
    assert items == []


def test_search_default_no_body_key(tmp_path: Path) -> None:
    """By default the returned item has no `body` key but DOES have `id`."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "my body text here"})
            result = await c.call_tool("search", {"text": "body"})
            content = _tc(dict, result.structured_content)
            items = content["items"]
            return items[0] if items else None

    item = asyncio.run(go())
    assert item is not None
    assert "id" in item
    assert "body" not in item


def test_search_include_body_true(tmp_path: Path) -> None:
    """With include_body=True the returned item HAS a `body` key
    equal to the full body text."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "full body content"})
            result = await c.call_tool("search", {"text": "body", "include_body": True})
            content = _tc(dict, result.structured_content)
            items = content["items"]
            return items[0] if items else None

    item = asyncio.run(go())
    assert item is not None
    assert "body" in item
    assert item["body"] == "full body content"
