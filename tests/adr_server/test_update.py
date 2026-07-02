import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.codec import parse_document
from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client, write_legacy_adrs


def test_update_status_transition_persists_and_preserves_title(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            # Create with default status "Proposed"
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "b",
                },
            )
            # Update status to Accepted
            result = await c.call_tool(
                "update",
                {
                    "id": "ADR-0007",
                    "status": "Accepted",
                },
            )
        data = (_tc(dict, result.structured_content))["item"]
        assert data["attributes"]["status"] == "Accepted"
        # title and other attributes survive
        assert data["attributes"]["title"] == "T"

    asyncio.run(go())


def test_update_invalid_status_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "b",
                },
            )
            return await c.call_tool(
                "update",
                {
                    "id": "ADR-0007",
                    "status": "Bogus",
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_update_missing_id_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "update",
                {
                    "id": "ADR-9999",
                    "status": "Accepted",
                },
            )

    with pytest.raises(ToolError, match=r"^not found: ADR-9999$"):
        asyncio.run(go())


@pytest.mark.parametrize("reserved_key", ["created", "updated", "id"])
def test_update_rejects_reserved_attributes(tmp_path: Path, reserved_key: str) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-0102", "title": "T", "body": "b"},
            )
            return await c.call_tool(
                "update",
                {
                    "id": "ADR-0102",
                    "attributes": {reserved_key: "x"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_update_legacy_record_migrates_timestamps(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    write_legacy_adrs(adr_dir / "seg", {"ADR-0001"})
    provider = StoreProvider(adr_dir, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            return await c.call_tool(
                "update",
                {"id": "ADR-0001", "status": "Superseded"},
            )

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["item"]["attributes"]["status"] == "Superseded"

    fm, _ = parse_document((adr_dir / "seg" / "ADR-0001.md").read_text(encoding="utf-8"))
    assert "date" not in fm
    assert str(fm["created"]) == "2026-06-29 00:00:00+00:00"
    assert fm["updated"] != fm["created"]


def test_update_preserves_existing_created_timestamp(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    (adr_dir / "seg").mkdir(parents=True)
    provider = StoreProvider(adr_dir, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-0101", "title": "Fresh", "body": "body"},
            )
            before = (adr_dir / "seg" / "ADR-0101.md").read_text(encoding="utf-8")
            before_fm, _ = parse_document(before)
            result = await c.call_tool(
                "update",
                {"id": "ADR-0101", "status": "Accepted"},
            )
            after_fm, _ = parse_document(
                (adr_dir / "seg" / "ADR-0101.md").read_text(encoding="utf-8")
            )
            return before_fm, after_fm, result

    before_fm, after_fm, result = asyncio.run(go())
    assert (_tc(dict, result.structured_content))["item"]["attributes"]["status"] == "Accepted"
    assert after_fm["created"] == before_fm["created"]
    assert after_fm["updated"] != before_fm["updated"]


def test_update_malformed_legacy_date_raises_tool_error(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    seg_dir = adr_dir / "seg"
    seg_dir.mkdir()
    (seg_dir / "ADR-0100.md").write_text(
        "---\nstatus: Accepted\ndate: not-a-real-date\ntitle: Bad\n---\nbody\n",
        encoding="utf-8",
    )
    provider = StoreProvider(adr_dir, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            return await c.call_tool(
                "update",
                {"id": "ADR-0100", "status": "Accepted"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_supersede_legacy_records_succeeds(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    write_legacy_adrs(adr_dir / "seg", {"ADR-0001", "ADR-0002"})
    provider = StoreProvider(adr_dir, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-0001", "new_id": "ADR-0002"},
            )

    r = asyncio.run(go())
    sc = _tc(dict, r.structured_content)
    assert sc["superseded"]["attributes"]["status"] == "Superseded"
    assert sc["superseded"]["attributes"]["superseded_by"] == "ADR-0002"
    assert sc["superseding"]["attributes"]["supersedes"] == "ADR-0001"
