"""Tests for the todo profile server (src/servers/todo.py)."""

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.markdown_store import MarkdownStore
from servers.todo import STATUS_VALUES, build_server


def _client(tmp_path: Path) -> Client:
    return Client(build_server(MarkdownStore(tmp_path)))


def test_health_returns_ok(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    assert r.data["status"] == "ok"


def test_health_reports_status_values(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    assert set(r.data["status_values"]) == STATUS_VALUES


def test_status_values_constant() -> None:
    assert {"todo", "in-progress", "done", "blocked"} == STATUS_VALUES


# ---------------------------------------------------------------------------
# _next_id unit tests
# ---------------------------------------------------------------------------

from servers.todo import _next_id, _next_order  # noqa: E402


def test_next_id_empty_partition(tmp_path: Path) -> None:
    """Empty store → "0001"."""
    store = MarkdownStore(tmp_path)
    assert _next_id(store) == "0001"


def test_next_id_after_sequential(tmp_path: Path) -> None:
    """After 0001, 0002 → next is 0003."""
    store = MarkdownStore(tmp_path)
    store.create("0001", attributes={})
    store.create("0002", attributes={})
    assert _next_id(store) == "0003"


def test_next_id_padding_width_4(tmp_path: Path) -> None:
    """With only 0001 present, next is 0002 (4 chars)."""
    store = MarkdownStore(tmp_path)
    store.create("0001", attributes={})
    assert _next_id(store) == "0002"
    assert len(_next_id(store)) == 4


def test_next_id_ignores_non_integer_stems(tmp_path: Path) -> None:
    """Non-integer stems (e.g. 'abc') are skipped; only pure int strings count."""
    store = MarkdownStore(tmp_path)
    store.create("abc", attributes={})
    store.create("0005", attributes={})
    assert _next_id(store) == "0006"


# ---------------------------------------------------------------------------
# _next_order unit tests
# ---------------------------------------------------------------------------


def test_next_order_empty_store(tmp_path: Path) -> None:
    """No entities → returns 1."""
    store = MarkdownStore(tmp_path)
    assert _next_order(store) == 1


def test_next_order_mixed_types(tmp_path: Path) -> None:
    """Bools are excluded; only int orders count."""
    store = MarkdownStore(tmp_path)
    store.create("0001", attributes={"order": True})
    store.create("0002", attributes={"order": 5})
    assert _next_order(store) == 6


# ---------------------------------------------------------------------------
# create tool tests
# ---------------------------------------------------------------------------


def test_create_defaults_status_and_order(tmp_path: Path) -> None:
    """Create with body: status==\"todo\", order==1, fresh id, body echoed."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "buy milk", "attributes": {}})

    r = asyncio.run(go())
    data = r.data
    assert data["attributes"]["status"] == "todo"
    assert data["attributes"]["order"] == 1
    assert data["body"] == "buy milk"


def test_create_order_increments(tmp_path: Path) -> None:
    """Creating twice: second item gets order==2 and larger id."""

    async def go():
        async with _client(tmp_path) as c:
            first = await c.call_tool("create", {"body": "first", "attributes": {}})
            second = await c.call_tool("create", {"body": "second", "attributes": {}})
        return first.data, second.data

    first, second = asyncio.run(go())
    assert first["attributes"]["order"] == 1
    assert second["attributes"]["order"] == 2
    assert second["id"] > first["id"]


def test_create_honours_custom_status(tmp_path: Path) -> None:
    """Passing attributes={\"status\": \"in-progress\"} is honored."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "wip item", "attributes": {"status": "in-progress"}},
            )

    r = asyncio.run(go())
    assert r.data["attributes"]["status"] == "in-progress"


def test_create_rejects_bogus_status(tmp_path: Path) -> None:
    """Passing attributes={\"status\": \"bogus\"} raises a tool error."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "bad status", "attributes": {"status": "bogus"}},
            )

    with pytest.raises(ToolError):
        asyncio.run(go())
