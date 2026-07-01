import asyncio
from pathlib import Path

from fastmcp import Client

from micro_entity.markdown_store import MarkdownStore
from servers.adr import build_server
from tests.adr_server.conftest import _client


def test_list_empty_partition(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert r.data["items"] == []
    assert r.data["errors"] == []


def test_list_sorted_after_two_adds(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "Second added", "body": "b"},
            )
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "First added", "body": "b"},
            )
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = r.data["items"]
    assert len(items) == 2
    assert r.data["errors"] == []
    assert items[0]["id"] == "ADR-0007"
    assert items[1]["id"] == "ADR-0008"


def test_list_migrates_legacy_record(tmp_path: Path) -> None:
    legacy_text = (
        "---\nid: ADR-0200\n"
        "title: Legacy record\n"
        "status: Accepted\ndate: 2026-06-29\n"
        "---\nLegacy body\n"
    )
    (tmp_path / "ADR-0200.md").write_text(legacy_text, encoding="utf-8")

    store = MarkdownStore(tmp_path)

    async def go():
        async with Client(build_server(store)) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = r.data["items"]
    errors = r.data["errors"]
    assert errors == []
    assert len(items) == 1
    assert items[0]["id"] == "ADR-0200"
    assert items[0]["attributes"]["title"] == "Legacy record"


def test_list_malformed_file_in_errors(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text("not a valid document\n", encoding="utf-8")

    store = MarkdownStore(tmp_path)

    async def go():
        async with Client(build_server(store)) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = r.data["items"]
    errors = r.data["errors"]
    assert items == []
    assert len(errors) == 1
    assert errors[0]["id"] == "bad"
