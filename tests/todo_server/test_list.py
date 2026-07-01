import asyncio
from pathlib import Path

from fastmcp import Client

from micro_entity.markdown_store import MarkdownStore
from servers.todo import build_server
from tests.todo_server.conftest import _client


def test_list_empty_partition(tmp_path: Path) -> None:
    """Empty partition → list returns both items and errors empty."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert r.data["items"] == []
    assert r.data["errors"] == []


def test_list_after_creating_two_items(tmp_path: Path) -> None:
    """After two create calls, list returns both in items, errors empty."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "first", "attributes": {}})
            await c.call_tool("create", {"body": "second", "attributes": {}})
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 2
    assert r.data["errors"] == []


def test_list_scales_malformed_files_as_errors(tmp_path: Path) -> None:
    """A malformed .md file appears in errors, not as a failure."""
    store = MarkdownStore(tmp_path)
    (tmp_path / "bad.md").write_text("not a valid document\n")

    async def go():
        async with Client(build_server(store)) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert len(r.data["errors"]) == 1
    assert r.data["errors"][0]["id"] == "bad"
