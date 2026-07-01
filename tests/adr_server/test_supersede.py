import asyncio
from pathlib import Path

import pytest

from micro_entity.codec import parse_document
from tests.adr_server.conftest import _client


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
