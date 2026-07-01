"""Tests for the ADR profile server (src/servers/adr.py)."""

import asyncio
import re
import shutil
from datetime import UTC, datetime
from datetime import date as date_cls
from pathlib import Path

import pytest
from fastmcp import Client

from micro_entity.codec import parse_document
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


def test_add_rejects_reserved_created_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "add",
                {
                    "id": "ADR-0011",
                    "title": "t",
                    "body": "b",
                    "attributes": {"created": "x"},
                },
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


@pytest.mark.parametrize("reserved_key", ["updated", "id"])
def test_add_rejects_other_reserved_attributes(tmp_path: Path, reserved_key: str) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "add",
                {
                    "id": "ADR-0012",
                    "title": "t",
                    "body": "b",
                    "attributes": {reserved_key: "x"},
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


@pytest.mark.parametrize("reserved_key", ["created", "updated", "id"])
def test_update_rejects_reserved_attributes(tmp_path: Path, reserved_key: str) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
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
    shutil.copytree(Path(__file__).resolve().parent.parent / "docs" / "adr", adr_dir)
    store = MarkdownStore(adr_dir)

    async def go():
        async with Client(build_server(store)) as c:
            return await c.call_tool(
                "update",
                {"id": "ADR-0001", "status": "Superseded"},
            )

    r = asyncio.run(go())
    assert r.data["attributes"]["status"] == "Superseded"

    fm, _ = parse_document((adr_dir / "ADR-0001.md").read_text(encoding="utf-8"))
    assert "date" not in fm
    assert str(fm["created"]) == "2026-06-29 00:00:00+00:00"
    assert fm["updated"] != fm["created"]


def test_update_preserves_existing_created_timestamp(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    shutil.copytree(Path(__file__).resolve().parent.parent / "docs" / "adr", adr_dir)
    store = MarkdownStore(adr_dir)

    async def go():
        async with Client(build_server(store)) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0101", "title": "Fresh", "body": "body"},
            )
            before = (adr_dir / "ADR-0101.md").read_text(encoding="utf-8")
            before_fm, _ = parse_document(before)
            result = await c.call_tool(
                "update",
                {"id": "ADR-0101", "status": "Accepted"},
            )
            after_fm, _ = parse_document((adr_dir / "ADR-0101.md").read_text(encoding="utf-8"))
            return before_fm, after_fm, result

    before_fm, after_fm, result = asyncio.run(go())
    assert result.data["attributes"]["status"] == "Accepted"
    assert after_fm["created"] == before_fm["created"]
    assert after_fm["updated"] != before_fm["updated"]


def test_supersede_legacy_records_succeeds(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    shutil.copytree(Path(__file__).resolve().parent.parent / "docs" / "adr", adr_dir)
    store = MarkdownStore(adr_dir)

    async def go():
        async with Client(build_server(store)) as c:
            return await c.call_tool(
                "supersede",
                {"old_id": "ADR-0001", "new_id": "ADR-0002"},
            )

    r = asyncio.run(go())
    assert r.data["superseded"]["attributes"]["status"] == "Superseded"
    assert r.data["superseded"]["attributes"]["superseded_by"] == "ADR-0002"
    assert r.data["superseding"]["attributes"]["supersedes"] == "ADR-0001"


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


def test_supersede_rolls_back_old_on_second_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import servers.adr as adr_mod

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

            old_path = tmp_path / "ADR-0007.md"
            before = old_path.read_text(encoding="utf-8")
            real_update = adr_mod.MarkdownStore.update

            def wrapper(store, ident, *, attributes=None, body=adr_mod.UNSET, normalize=None):
                if ident == "ADR-0008":
                    raise RuntimeError("boom")
                return real_update(
                    store,
                    ident,
                    attributes=attributes,
                    body=body,
                    normalize=normalize,
                )

            monkeypatch.setattr(adr_mod.MarkdownStore, "update", wrapper)

            result = await c.call_tool(
                "supersede",
                {"old_id": "ADR-0007", "new_id": "ADR-0008"},
                raise_on_error=False,
            )
            after = old_path.read_text(encoding="utf-8")
            fm, _ = parse_document(after)
            return before, after, fm, result

    before, after, fm, result = asyncio.run(go())
    assert result.is_error is True
    assert after == before
    assert fm["status"] != "Superseded"
    assert "superseded_by" not in fm


def test_supersede_missing_old_leaves_new_untouched(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "add",
                {"id": "ADR-0008", "title": "New", "body": "b"},
            )
            new_path = tmp_path / "ADR-0008.md"
            before = new_path.read_text(encoding="utf-8")
            result = await c.call_tool(
                "supersede",
                {"old_id": "ADR-9999", "new_id": "ADR-0008"},
                raise_on_error=False,
            )
            after = new_path.read_text(encoding="utf-8")
            return before, after, result

    before, after, result = asyncio.run(go())
    assert result.is_error is True
    assert after == before


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


# ---------------------------------------------------------------------------
# Dogfooding — real ADR files load cleanly
# ---------------------------------------------------------------------------

ADR_SRC = Path(__file__).resolve().parent.parent / "docs" / "adr"


def test_dogfood_real_adr_files_all_load(tmp_path: Path) -> None:
    """Prove every real ADR in ``docs/adr/`` loads through the migrated path."""
    # 1. Copy real files into tmp_path
    src_files = sorted(ADR_SRC.glob("*.md"))
    copied = 0
    for src in src_files:
        shutil.copy2(src, tmp_path / src.name)
        copied += 1

    # Guard: we actually found the files
    assert copied >= 5, f"Expected >= 5 ADR files under {ADR_SRC}, got {copied}"

    # Snapshot filename stems for later id-matching
    filename_stems = {f.stem for f in src_files}

    # 2. Build a client over a store at tmp_path
    store = MarkdownStore(tmp_path)
    client = Client(build_server(store))

    # 3. Call the list tool
    async def go():
        async with client as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    data = r.data
    items = data["items"]
    errors = data["errors"]

    # 4. ZERO unexplained quarantines
    assert errors == [], f"ADR files quarantined: {errors}"

    # 5. Item count == file count
    assert len(items) == copied

    ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    # 6. Per-item assertions
    item_ids = set()
    has_tags_member = False
    for item in items:
        item_id = item["id"]
        item_ids.add(item_id)

        # id matches a copied filename stem
        assert item_id in filename_stems, f"Item id {item_id!r} does not match any copied file stem"

        # status is valid
        status = item["attributes"]["status"]
        assert status in STATUS_VALUES, f"{item_id}: unexpected status {status!r}"

        # non-empty body
        assert item.get("body"), f"{item_id}: missing body"

        # migrated created/updated as ISO-8601 strings
        created = item.get("created")
        updated = item.get("updated")
        assert created is not None and isinstance(created, str), (
            f"{item_id}: missing/invalid created"
        )
        assert updated is not None and isinstance(updated, str), (
            f"{item_id}: missing/invalid updated"
        )
        assert ISO_RE.match(created), f"{item_id}: created not ISO-8601: {created}"
        assert ISO_RE.match(updated), f"{item_id}: updated not ISO-8601: {updated}"

        # 7. Relation/attribute keys: every item has title
        assert "title" in item["attributes"], f"{item_id}: missing title"
        if "tags" in item["attributes"] and item["attributes"]["tags"]:
            has_tags_member = True

    assert has_tags_member, "No item has a tags attribute; expected at least one"
