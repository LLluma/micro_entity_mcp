import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.todo_server.conftest import _client


def test_query_filter_by_status(tmp_path: Path) -> None:
    """Create three items; update one to blocked;
    query({"status": ["blocked"]}) returns only that one."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "item one", "attributes": {}})
            await c.call_tool("create", {"body": "item two", "attributes": {}})
            await c.call_tool("create", {"body": "item three", "attributes": {}})
            await c.call_tool("update", {"id": "0002", "status": "blocked"})
            return await c.call_tool("query", {"criteria": {"status": ["blocked"]}})

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["items"]) == 1
    assert (_tc(dict, r.structured_content))["items"][0]["attributes"]["status"] == "blocked"


def test_query_empty_criteria_returns_all(tmp_path: Path) -> None:
    """query({}) (no args) returns ALL items."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "one", "attributes": {}})
            await c.call_tool("create", {"body": "two", "attributes": {}})
            await c.call_tool("create", {"body": "three", "attributes": {}})
            r1 = await c.call_tool("query", {"criteria": {}})
            r2 = await c.call_tool("query", {})
            items1 = (_tc(dict, r1.structured_content))["items"]
            items2 = (_tc(dict, r2.structured_content))["items"]
            return items1, items2

    all_items, no_args_items = asyncio.run(go())
    assert len(all_items) == 3
    assert len(no_args_items) == 3


def test_query_no_matches_returns_empty(tmp_path: Path) -> None:
    """query({"status": ["nonexistent-status"]}) → items == []."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "one", "attributes": {}})
            return await c.call_tool("query", {"criteria": {"status": ["nonexistent-status"]}})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["items"] == []


def test_query_membership_or_within_key(tmp_path: Path) -> None:
    """Create items with status todo and done;
    query({"status": ["todo", "done"]}) returns both."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "todo item", "attributes": {"status": "todo"}},
            )
            await c.call_tool(
                "create",
                {"body": "done item", "attributes": {"status": "done"}},
            )
            return await c.call_tool("query", {"criteria": {"status": ["todo", "done"]}})

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["items"]) == 2


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
