"""Tests for the ADR profile server (src/servers/adr.py)."""

import asyncio
from datetime import UTC, datetime
from datetime import date as date_cls
from pathlib import Path

from fastmcp import Client

from micro_entity.markdown_store import MarkdownStore
from servers.adr import STATUS_VALUES, _normalize_frontmatter, build_server


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
    assert {"Proposed", "Accepted", "Superseded"} == STATUS_VALUES


# ---------------------------------------------------------------------------
# _normalize_frontmatter
# ---------------------------------------------------------------------------


def test_normalize_date_as_datetime_date() -> None:
    fm: dict = {"date": date_cls(2026, 6, 29)}
    result = _normalize_frontmatter(fm)
    expected = datetime(2026, 6, 29, tzinfo=UTC)
    assert result is fm
    assert fm["created"] == expected
    assert fm["updated"] == expected


def test_normalize_date_as_string() -> None:
    fm: dict = {"date": "2026-06-29"}
    result = _normalize_frontmatter(fm)
    expected = datetime(2026, 6, 29, tzinfo=UTC)
    assert result is fm
    assert fm["created"] == expected
    assert fm["updated"] == expected


def test_normalize_skip_existing_timestamps() -> None:
    existing_created = datetime(2025, 1, 1, tzinfo=UTC)
    existing_updated = datetime(2025, 6, 15, tzinfo=UTC)
    fm: dict = {
        "created": existing_created,
        "updated": existing_updated,
        "date": datetime(2026, 6, 29, tzinfo=UTC),
    }
    result = _normalize_frontmatter(fm)
    assert result is fm
    assert fm["created"] is existing_created
    assert fm["updated"] is existing_updated


def test_normalize_no_date_no_timestamps() -> None:
    fm: dict = {"title": "no date here"}
    result = _normalize_frontmatter(fm)
    assert result is fm
    assert "created" not in fm
    assert "updated" not in fm


def test_normalize_datetime_datetime_drops_time() -> None:
    fm: dict = {"date": datetime(2026, 6, 29, 13, 30, tzinfo=UTC)}
    result = _normalize_frontmatter(fm)
    expected = datetime(2026, 6, 29, tzinfo=UTC)
    assert result is fm
    assert fm["created"] == expected
    assert fm["updated"] == expected


# ---------------------------------------------------------------------------
# add tool
# ---------------------------------------------------------------------------


def test_add_returns_entity_dict(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "add",
                {
                    "id": "ADR-0007",
                    "title": "Some decision",
                    "body": "prose",
                },
            )

    r = asyncio.run(go())
    data = r.data
    assert data["id"] == "ADR-0007"
    assert data["attributes"]["title"] == "Some decision"
    assert data["attributes"]["status"] == "Proposed"
    assert data["body"] == "prose"


def test_add_duplicate_id_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0008",
                    "title": "First",
                    "body": "b",
                },
            )
            result = await c.call_tool(
                "add",
                {
                    "id": "ADR-0008",
                    "title": "Second",
                    "body": "b",
                },
                raise_on_error=False,
            )
        assert result.is_error is True

    asyncio.run(go())


def test_add_invalid_status_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "add",
                {
                    "id": "ADR-0009",
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "Bogus"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_add_custom_valid_status_honored(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "add",
                {
                    "id": "ADR-0010",
                    "title": "t",
                    "body": "b",
                    "attributes": {"status": "Accepted"},
                },
            )

    r = asyncio.run(go())
    data = r.data
    assert data["attributes"]["status"] == "Accepted"


# ---------------------------------------------------------------------------
# get tool
# ---------------------------------------------------------------------------


def test_get_returns_added_entity(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "prose",
                },
            )
            return await c.call_tool("get", {"id": "ADR-0007"})

    r = asyncio.run(go())
    data = r.data
    assert data["id"] == "ADR-0007"
    assert data["attributes"]["title"] == "T"
    assert data["body"] == "prose"


def test_get_legacy_migration(tmp_path: Path) -> None:
    # Write a legacy record (only ``date``, no created/updated)
    (tmp_path / "ADR-0100.md").write_text(
        "---\nid: ADR-0100\ntitle: Legacy\nstatus: Accepted\ndate: 2026-06-29\n---\nLegacy body\n",
        encoding="utf-8",
    )

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "ADR-0100"})

    r = asyncio.run(go())
    data = r.data
    assert data["attributes"]["title"] == "Legacy"
    # Migrated timestamps should be midnight UTC of the date
    assert data["created"] == "2026-06-29T00:00:00Z"
    assert data["updated"] == "2026-06-29T00:00:00Z"


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
