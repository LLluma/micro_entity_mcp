import asyncio
import shutil
import tempfile
from pathlib import Path

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
                    "id": "ADR-0001",
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
        diff_text = r1.data["diff"]
        assert isinstance(diff_text, str)
        assert diff_text  # non-empty
        # diff to=None is ref vs working tree — working tree = HEAD content
        assert "CHANGED_BODY_XYZ" in diff_text

        diff_text2 = r2.data["diff"]
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
                    "id": "ADR-0002",
                    "title": "T",
                    "body": "BODY",
                },
            )
            r = await c.call_tool(
                "diff",
                {
                    "id": "ADR-0002",
                    "ref": "HEAD",
                    "to": "HEAD",
                },
            )
        assert r.data["diff"] == ""

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
