import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import cast as _tc

from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client


def test_diff_between_ref_and_head(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "T",
                    "body": "ORIGINAL_BODY",
                },
            )
            await c.call_tool(
                "update",
                {
                    "id": "ADR-0001",
                    "body": "CHANGED_BODY_XYZ",
                    "status": "Accepted",
                },
            )
            r1 = await c.call_tool(
                "diff",
                {
                    "id": "ADR-0001",
                    "ref": "HEAD~1",
                },
            )
            r2 = await c.call_tool(
                "diff",
                {
                    "id": "ADR-0001",
                    "ref": "HEAD~1",
                    "to": "HEAD",
                },
            )
        diff_text = (_tc(dict, r1.structured_content))["diff"]
        assert isinstance(diff_text, str)
        assert diff_text  # non-empty
        # diff to=None is ref vs working tree — working tree = HEAD content
        assert "CHANGED_BODY_XYZ" in diff_text

        diff_text2 = (_tc(dict, r2.structured_content))["diff"]
        assert isinstance(diff_text2, str)
        assert diff_text2  # non-empty
        assert "CHANGED_BODY_XYZ" in diff_text2

    asyncio.run(go())


def test_diff_same_ref_to_head_is_empty(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "T",
                    "body": "BODY",
                },
            )
            r = await c.call_tool(
                "diff",
                {
                    "id": "ADR-0001",
                    "ref": "HEAD",
                    "to": "HEAD",
                },
            )
        assert (_tc(dict, r.structured_content))["diff"] == ""

    asyncio.run(go())


def test_diff_no_ref_after_update(tmp_path: Path) -> None:
    """diff(id) with no ref args returns the last-change diff (created+updated -> 2 commits)."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "T",
                    "body": "ORIGINAL_BODY",
                },
            )
            await c.call_tool(
                "update",
                {
                    "id": "ADR-0001",
                    "body": "UPDATED_BODY_ABC",
                    "status": "Accepted",
                },
            )
            r = await c.call_tool("diff", {"id": "ADR-0001"})
        diff_text = (_tc(dict, r.structured_content))["diff"]
        assert isinstance(diff_text, str)
        assert diff_text  # non-empty — last commit changed body
        assert "UPDATED_BODY_ABC" in diff_text

    asyncio.run(go())


def test_diff_no_ref_fresh_adr(tmp_path: Path) -> None:
    """diff(id) with no ref on a freshly-created ADR shows its content as an addition."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "T",
                    "body": "FRESH_BODY",
                },
            )
            r = await c.call_tool("diff", {"id": "ADR-0001"})
        diff_text = (_tc(dict, r.structured_content))["diff"]
        assert isinstance(diff_text, str)
        assert diff_text  # non-empty — initial commit shows file as addition
        assert "FRESH_BODY" in diff_text

    asyncio.run(go())


def test_diff_explicit_range(tmp_path: Path) -> None:
    """diff(id, ref='HEAD~1', to='HEAD') still works as an explicit range."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"title": "T", "body": "ORIGINAL"},
            )
            await c.call_tool(
                "update",
                {"id": "ADR-0001", "body": "CHANGED", "status": "Accepted"},
            )
            r = await c.call_tool(
                "diff",
                {"id": "ADR-0001", "ref": "HEAD~1"},
            )
        diff_text = (_tc(dict, r.structured_content))["diff"]
        assert diff_text  # non-empty
        # working tree = HEAD content (auto-commit), so ref vs working = ref vs HEAD
        assert "CHANGED" in diff_text

    asyncio.run(go())


def test_diff_not_found_guard(tmp_path: Path) -> None:
    """diff(nonexistent_id) raises 'not found: <id>' guard preserved."""

    async def go():
        async with _client(tmp_path) as c:
            r = await c.call_tool(
                "diff",
                {"id": "NOPE-ID", "ref": "HEAD"},
                raise_on_error=False,
            )
        assert r.is_error is True
        content_list = r.content or []
        errmsg = content_list[0].text if content_list and content_list[0].type == "text" else ""
        assert "not found: NOPE-ID" in errmsg

    asyncio.run(go())


def test_diff_non_git_store_raises_tool_error() -> None:
    tmpdir = tempfile.mkdtemp()
    try:
        nogit = Path(tmpdir) / "norepo"
        nogit.mkdir()
        provider = StoreProvider(nogit, "seg")
        server = build_server(provider)

        async def go():
            async with Client(server) as c:
                return await c.call_tool(
                    "diff",
                    {
                        "id": "ADR-0001",
                        "ref": "HEAD",
                    },
                    raise_on_error=False,
                )

        r = asyncio.run(go())
        assert r.is_error is True
        content_list = r.content or []
        errmsg = content_list[0].text if content_list and content_list[0].type == "text" else ""
        assert "storage is not under git" in errmsg
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
