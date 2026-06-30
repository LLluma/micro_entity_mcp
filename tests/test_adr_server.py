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


# ---------------------------------------------------------------------------
# list tool  (_load_all_migrated)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# update tool
# ---------------------------------------------------------------------------


def test_update_status_transition_persists_and_preserves_title(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            # Create with default status "Proposed"
            await c.call_tool(
                "add",
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
        data = result.data
        assert data["attributes"]["status"] == "Accepted"
        # title and other attributes survive
        assert data["attributes"]["title"] == "T"

    asyncio.run(go())


def test_update_invalid_status_raises_tool_error(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
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
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


# ---------------------------------------------------------------------------
# supersede tool
# ---------------------------------------------------------------------------


def test_supersede_sets_pointers(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "Old", "body": "b"},
            )
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "New", "body": "b"},
            )
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-0007", "new_id": "ADR-0008"},
            )

    r = asyncio.run(go())
    data = r.data
    assert data["superseded"]["attributes"]["status"] == "Superseded"
    assert data["superseded"]["attributes"]["superseded_by"] == "ADR-0008"
    assert data["superseding"]["attributes"]["supersedes"] == "ADR-0007"


def test_supersede_status_is_clean_enum(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "Old", "body": "b"},
            )
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "New", "body": "b"},
            )
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-0007", "new_id": "ADR-0008"},
            )

    r = asyncio.run(go())
    status_val = r.data["superseded"]["attributes"]["status"]
    assert status_val == "Superseded"
    assert "by" not in status_val


def test_supersede_missing_old_raises(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "New", "body": "b"},
            )
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-9999", "new_id": "ADR-0008"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


def test_supersede_missing_new_raises(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "Old", "body": "b"},
            )
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-0007", "new_id": "ADR-9999"},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


# ---------------------------------------------------------------------------
# query tool
# ---------------------------------------------------------------------------


def test_query_filter_by_tags(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "b",
                    "attributes": {"tags": ["durable"]},
                },
            )
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0008",
                    "title": "T",
                    "body": "b",
                    "attributes": {"tags": ["ephemeral"]},
                },
            )
            return await c.call_tool(
                "query",
                {"criteria": {"tags": ["durable"]}},
            )

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0007"


def test_query_filter_by_status(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "update",
                {"id": "ADR-0007", "status": "Accepted"},
            )
            return await c.call_tool(
                "query",
                {"criteria": {"status": ["Accepted"]}},
            )

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0007"


def test_query_empty_returns_all(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "T2", "body": "b2"},
            )
            return await c.call_tool("query", {})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 2


def test_query_no_match_empty(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0007", "title": "T", "body": "b"},
            )
            return await c.call_tool(
                "query",
                {"criteria": {"tags": ["nonexistent"]}},
            )

    r = asyncio.run(go())
    assert r.data["items"] == []


# ---------------------------------------------------------------------------
# search tool
# ---------------------------------------------------------------------------


def test_search_matches_body_substring(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0007",
                    "title": "T",
                    "body": "The quick brown fox",
                },
            )
            return await c.call_tool("search", {"text": "quick"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0007"


def test_search_matches_tag_value(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0008",
                    "title": "T2",
                    "body": "nothing",
                    "attributes": {"tags": ["durable", "schema"]},
                },
            )
            return await c.call_tool("search", {"text": "durable"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0008"


def test_search_case_insensitive(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0009",
                    "title": "Case test",
                    "body": "The Quick Brown Fox",
                },
            )
            return await c.call_tool("search", {"text": "QUICK"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0009"


def test_search_no_match_returns_empty(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0010",
                    "title": "T",
                    "body": "nothing here",
                },
            )
            return await c.call_tool("search", {"text": "zzzznomatch"})

    r = asyncio.run(go())
    assert r.data["items"] == []


def test_search_matches_title_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {
                    "id": "ADR-0009",
                    "title": "Persistence Layer",
                    "body": "x",
                },
            )
            return await c.call_tool("search", {"text": "persistence"})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["id"] == "ADR-0009"
