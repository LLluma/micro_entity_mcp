"""Tests for the todo profile server (src/servers/todo.py)."""

import asyncio
from pathlib import Path

from fastmcp import Client

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

from servers.todo import _next_id  # noqa: E402


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
