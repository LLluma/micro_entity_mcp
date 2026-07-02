import asyncio
from pathlib import Path

from fastmcp import Client

from micro_entity.markdown_store import MarkdownStore
from micro_entity.partition import StoreProvider
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


def test_list_default_strips_body(tmp_path: Path) -> None:
    """Default list (include_body=False) returns items without a body key."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "my todo body"})
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    item = r.data["items"][0]
    assert "body" not in item
    assert "id" in item
    assert "attributes" in item
    assert item["attributes"]["status"] == "todo"
    assert "order" in item["attributes"]
    assert isinstance(r.data["errors"], list)


def test_list_include_body_true_keeps_body(tmp_path: Path) -> None:
    """list with include_body=True returns items that contain a body key."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "secret todo body"})
            return await c.call_tool("list", {"include_body": True})

    r = asyncio.run(go())
    item = r.data["items"][0]
    assert "body" in item
    assert item["body"] == "secret todo body"
    assert isinstance(r.data["errors"], list)


def test_list_scales_malformed_files_as_errors(tmp_path: Path) -> None:
    """A malformed .md file appears in errors, not as a failure."""
    MarkdownStore(tmp_path, segment="seg")  # ensures tmp_path/seg exists
    (tmp_path / "seg" / "bad.md").write_text("not a valid document\n")
    provider = StoreProvider(tmp_path, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert len(r.data["errors"]) == 1
    assert r.data["errors"][0]["id"] == "bad"
