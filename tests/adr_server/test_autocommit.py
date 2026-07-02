import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastmcp import Client

from micro_entity import vcs
from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client


def _repo_root(tmp_path: Path) -> Path:
    return tmp_path  # seg dir is tmp_path/"seg", root is tmp_path


# ---------------------------------------------------------------------------
# create auto-commits
# ---------------------------------------------------------------------------


def test_create_auto_commits(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0001", "title": "T", "body": "B"})

    asyncio.run(go())
    root = _repo_root(tmp_path)
    fpath = tmp_path / "seg" / "ADR-0001.md"
    log = vcs.file_log(root, fpath, limit=10)
    assert len(log) >= 1
    assert log[0]["message"] == "create adr ADR-0001"


# ---------------------------------------------------------------------------
# create + update auto-commits
# ---------------------------------------------------------------------------


def test_create_and_update_auto_commits(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0001", "title": "T", "body": "B"})
            await c.call_tool("update", {"id": "ADR-0001", "status": "Accepted"})

    asyncio.run(go())
    root = _repo_root(tmp_path)
    fpath = tmp_path / "seg" / "ADR-0001.md"
    log = vcs.file_log(root, fpath, limit=10)
    assert len(log) >= 2
    assert log[0]["message"] == "update adr ADR-0001"


# ---------------------------------------------------------------------------
# patch_body auto-commit
# ---------------------------------------------------------------------------


def test_create_and_patch_body_auto_commits(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0001", "title": "T", "body": "old body"})
            await c.call_tool(
                "patch_body",
                {"id": "ADR-0001", "old": "old body", "new": "new body"},
            )

    asyncio.run(go())
    root = _repo_root(tmp_path)
    fpath = tmp_path / "seg" / "ADR-0001.md"
    log = vcs.file_log(root, fpath, limit=10)
    assert len(log) >= 2
    assert log[0]["message"] == "patch_body adr ADR-0001"


# ---------------------------------------------------------------------------
# supersede auto-commits
# ---------------------------------------------------------------------------


def test_supersede_single_commit_touched_both_files(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"id": "ADR-0001", "title": "First", "body": "B1"})
            await c.call_tool("create", {"id": "ADR-0002", "title": "Second", "body": "B2"})
            await c.call_tool(
                "supersede",
                {"old_id": "ADR-0001", "new_id": "ADR-0002"},
            )

    asyncio.run(go())
    root = _repo_root(tmp_path)

    # HEAD commit touches both files
    show = subprocess.run(
        ["git", "-C", str(root), "show", "--name-only", "--format=", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    output = show.stdout
    assert "seg/ADR-0001.md" in output
    assert "seg/ADR-0002.md" in output

    # Commit message
    fpath = tmp_path / "seg" / "ADR-0001.md"
    log = vcs.file_log(root, fpath, limit=10)
    assert log[0]["message"] == "supersede adr ADR-0001 -> ADR-0002"


# ---------------------------------------------------------------------------
# non-git store raises ToolError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_name,args",
    [
        ("create", {"id": "ADR-0001", "title": "T", "body": "B"}),
        ("update", {"id": "ADR-0001", "status": "Accepted"}),
        ("patch_body", {"id": "ADR-0001", "old": "x", "new": "y"}),
        ("supersede", {"old_id": "ADR-0001", "new_id": "ADR-0002"}),
    ],
)
def test_non_git_store_raises_tool_error(tmp_path: Path, tool_name: str, args: dict) -> None:
    nogit = tempfile.mkdtemp()
    provider = StoreProvider(Path(nogit), "seg")
    try:
        c = Client(build_server(provider))

        async def go():
            async with c:
                r = await c.call_tool(tool_name, args, raise_on_error=False)
                return r

        r = asyncio.run(go())
    finally:
        shutil.rmtree(nogit, ignore_errors=True)

    assert r.is_error is True
    content_list = r.content or []
    errmsg = content_list[0].text if content_list and content_list[0].type == "text" else ""
    assert "storage is not under git" in errmsg
