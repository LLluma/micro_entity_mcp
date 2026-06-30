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
