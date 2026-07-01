import asyncio
from pathlib import Path

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
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["attributes"]["status"] == "blocked"


def test_query_empty_criteria_returns_all(tmp_path: Path) -> None:
    """query({}) (no args) returns ALL items."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "one", "attributes": {}})
            await c.call_tool("create", {"body": "two", "attributes": {}})
            await c.call_tool("create", {"body": "three", "attributes": {}})
            r1 = await c.call_tool("query", {"criteria": {}})
            r2 = await c.call_tool("query", {})
            return r1.data["items"], r2.data["items"]

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
    assert r.data["items"] == []


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
    assert len(r.data["items"]) == 2
