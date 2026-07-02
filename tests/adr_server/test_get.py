import asyncio
from pathlib import Path

from tests.adr_server.conftest import _client


def test_get_returns_added_entity(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "prose",
                },
            )
            return await c.call_tool("get", {"id": "ADR-0007"})

    r = asyncio.run(go())
    data = r.data
    assert data["item"]["id"] == "ADR-0007"
    assert data["item"]["attributes"]["title"] == "T"
    assert data["item"]["body"] == "prose"


def test_get_legacy_migration(tmp_path: Path) -> None:
    # Write a legacy record (only ``date``, no created/updated)
    seg_dir = tmp_path / "seg"
    seg_dir.mkdir()
    (seg_dir / "ADR-0100.md").write_text(
        "---\nid: ADR-0100\ntitle: Legacy\nstatus: Accepted\ndate: 2026-06-29\n---\nLegacy body\n",
        encoding="utf-8",
    )

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "ADR-0100"})

    r = asyncio.run(go())
    data = r.data
    assert data["item"]["attributes"]["title"] == "Legacy"
    # Migrated timestamps should be midnight UTC of the date
    assert data["item"]["created"] == "2026-06-29T00:00:00Z"
    assert data["item"]["updated"] == "2026-06-29T00:00:00Z"


def test_get_missing_id_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "get",
                {"id": "ADR-9999"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_get_malformed_legacy_date_raises_tool_error(tmp_path: Path) -> None:
    seg_dir = tmp_path / "seg"
    seg_dir.mkdir()
    (seg_dir / "ADR-0099.md").write_text(
        "---\nstatus: Accepted\ndate: not-a-real-date\ntitle: Bad\n---\nbody\n",
        encoding="utf-8",
    )

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "get",
                {"id": "ADR-0099"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True
