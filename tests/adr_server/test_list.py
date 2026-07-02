import asyncio
from pathlib import Path

from fastmcp import Client

from micro_entity.partition import StoreProvider
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
                "create",
                {"id": "ADR-0008", "title": "Second added", "body": "b"},
            )
            await c.call_tool(
                "create",
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
    seg_dir = tmp_path / "seg"
    seg_dir.mkdir()
    (seg_dir / "ADR-0200.md").write_text(legacy_text, encoding="utf-8")

    provider = StoreProvider(tmp_path, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = r.data["items"]
    errors = r.data["errors"]
    assert errors == []
    assert len(items) == 1
    assert items[0]["id"] == "ADR-0200"
    assert items[0]["attributes"]["title"] == "Legacy record"


def test_list_malformed_file_in_errors(tmp_path: Path) -> None:
    seg_dir = tmp_path / "seg"
    seg_dir.mkdir()
    (seg_dir / "bad.md").write_text("not a valid document\n", encoding="utf-8")

    provider = StoreProvider(tmp_path, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = r.data["items"]
    errors = r.data["errors"]
    assert items == []
    assert len(errors) == 1
    assert errors[0]["id"] == "bad"


# ---------------------------------------------------------------------------
# include_body parameter
# ---------------------------------------------------------------------------


def test_list_default_strips_body(tmp_path: Path) -> None:
    """With no include_body argument, items must NOT contain a body key."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-9001", "title": "T", "body": "b"})
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = r.data["items"]
    assert len(items) >= 1, "Need at least one ADR to assert"
    for item in items:
        assert "body" not in item, (
            f"Default list should not include body; got keys: {list(item.keys())}"
        )


def test_list_include_body_true_includes_body(tmp_path: Path) -> None:
    """With include_body=True, items MUST contain a body key."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-9002", "title": "T", "body": "b"})
            return await c.call_tool("list", {"include_body": True})

    r = asyncio.run(go())
    items = r.data["items"]
    assert len(items) >= 1, "Need at least one ADR to assert"
    for item in items:
        assert "body" in item, f"include_body=True must include body; got keys: {list(item.keys())}"


def test_list_default_preserves_id_attributes(tmp_path: Path) -> None:
    """Default (stripped) items still carry id, attributes with title/status."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-9003",
                    "title": "MyTitle",
                    "body": "b",
                    "attributes": {"status": "Accepted"},
                },
            )
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = r.data["items"]
    items_by_id = {it["id"]: it for it in items}
    adr = items_by_id["ADR-9003"]
    assert "id" in adr
    assert "attributes" in adr
    assert "title" in adr["attributes"]
    assert "status" in adr["attributes"]
