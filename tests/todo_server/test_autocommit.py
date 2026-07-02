"""Auto-commit tests: every mutation commits the entity file to git."""

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp import Client

from micro_entity import vcs
from micro_entity.partition import StoreProvider
from servers.todo import build_server
from tests.todo_server.conftest import _client

# ---------------------------------------------------------------------------
# Positive: git-backed store
# ---------------------------------------------------------------------------


def test_create_commits_entity(tmp_path: Path) -> None:
    """After create, file_log for the entity shows one commit with message."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "auto-commit create test"},
            )
            item_id = (_tc(dict, created.structured_content))["item"]["id"]
        root = vcs.find_repo_root(tmp_path)
        entity_path = root / "test" / f"{item_id}.md"
        entries = vcs.file_log(root, entity_path, limit=10)
        return entries, item_id

    entries, item_id = asyncio.run(go())
    assert len(entries) == 1
    assert entries[0]["message"] == f"create todo {item_id}"


def test_update_commits_entity_after_create(tmp_path: Path) -> None:
    """After create then update, file_log shows update commit at top."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "update-auto-commit"},
            )
            item_id = (_tc(dict, created.structured_content))["item"]["id"]
            await c.call_tool("update", {"id": item_id, "status": "done"})
        root = vcs.find_repo_root(tmp_path)
        entity_path = root / "test" / f"{item_id}.md"
        entries = vcs.file_log(root, entity_path, limit=10)
        return entries

    entries = asyncio.run(go())
    assert len(entries) >= 2
    assert entries[0]["message"] == "update todo 0001"
    assert entries[1]["message"] == "create todo 0001"


def test_patch_body_commits_entity(tmp_path: Path) -> None:
    """After create then patch_body, file_log shows patch_body commit."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "patch original text here"},
            )
            await c.call_tool("patch_body", {"id": "0001", "old": "original", "new": "modified"})
        root = vcs.find_repo_root(tmp_path)
        entity_path = root / "test" / "0001.md"
        entries = vcs.file_log(root, entity_path, limit=10)
        return entries

    entries = asyncio.run(go())
    assert len(entries) >= 2
    assert entries[0]["message"] == "patch_body todo 0001"


def test_delete_commits_entity_deleted(tmp_path: Path) -> None:
    """After create then delete, commit exists and file gone from disk."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "delete-auto-commit"},
            )
            item_id = (_tc(dict, created.structured_content))["item"]["id"]
            await c.call_tool("delete", {"id": item_id})
        root = vcs.find_repo_root(tmp_path)
        entity_path = root / "test" / f"{item_id}.md"
        entries = vcs.file_log(root, entity_path, limit=10)
        exists = entity_path.exists()
        return entries, exists, item_id

    entries, exists, item_id = asyncio.run(go())
    assert len(entries) >= 2
    assert entries[0]["message"] == f"delete todo {item_id}"
    assert not exists


def test_commit_touched_only_that_file(tmp_path: Path) -> None:
    """Each mutation commit touches ONLY the entity's file."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "single-file commit test"},
            )
            item_id = (_tc(dict, created.structured_content))["item"]["id"]
            root = vcs.find_repo_root(tmp_path)
            entity_path = root / "test" / f"{item_id}.md"
            entries = vcs.file_log(root, entity_path, limit=3)
        return entries, item_id, root

    entries, item_id, root = asyncio.run(go())
    assert len(entries) == 1
    entry_sha = entries[0]["sha"]
    changed_files = subprocess_check(root, item_id, entry_sha)
    # Only 1 changed file — the entity itself
    assert len(changed_files) == 1
    assert f"test/{item_id}.md" in changed_files[0]


# ---------------------------------------------------------------------------
# Negative: non-git store — every mutation must fail fast
# ---------------------------------------------------------------------------


def _make_nogit_client() -> tuple[Path, Client]:
    """Return (nogit_path, client) on a truly non-git directory under system temp."""
    nogit = Path(tempfile.mkdtemp(prefix="_nogit_"))
    # Safety guard: verify this directory is genuinely NOT inside a git repo.
    with pytest.raises(vcs.NotAGitRepoError):
        vcs.find_repo_root(nogit)
    client = Client(build_server(StoreProvider(nogit, "test")))
    return nogit, client


def _cleanup_nogit(nogit: Path) -> None:
    """Remove a non-git temp directory created by ``_make_nogit_client``."""
    shutil.rmtree(nogit, ignore_errors=True)


def test_non_git_create_raises_tool_error(tmp_path: Path) -> None:
    """Create on non-git store raises ToolError('storage is not under git')."""
    nogit, client = _make_nogit_client()
    try:

        async def go():
            async with client:
                return await client.call_tool(
                    "create",
                    {"body": "no-git test"},
                    raise_on_error=False,
                )

        r = asyncio.run(go())
        assert r.is_error is True
        content_list = r.content or []
        errmsg = content_list[0].text if content_list and content_list[0].type == "text" else ""
        assert "storage is not under git" in errmsg
        # No file should have been written
        test_dir = nogit / "test"
        assert not test_dir.exists() or len(list(test_dir.iterdir())) == 0
    finally:
        _cleanup_nogit(nogit)


def test_non_git_update_raises_tool_error(tmp_path: Path) -> None:
    """Update on non-git store raises same error (even without any entity)."""
    _non_git_raises("update", {"id": "0099", "status": "done"})


def test_non_git_patch_body_raises_tool_error(tmp_path: Path) -> None:
    """Patch_body on non-git store raises same error."""
    _non_git_raises("patch_body", {"id": "0099", "old": "foo", "new": "bar"})


def test_non_git_delete_raises_tool_error(tmp_path: Path) -> None:
    """Delete on non-git store raises same error."""
    _non_git_raises("delete", {"id": "0099"})


def _non_git_raises(tool_name: str, args: dict) -> None:
    """Build client on non-git store, call *tool*, assert ToolError."""
    nogit, client = _make_nogit_client()
    try:

        async def go() -> None:
            async with client:
                r = await client.call_tool(tool_name, args, raise_on_error=False)
                assert r.is_error is True
                content_list = r.content or []
                errmsg = (
                    content_list[0].text if content_list and content_list[0].type == "text" else ""
                )
                assert "storage is not under git" in errmsg

        asyncio.run(go())
    finally:
        _cleanup_nogit(nogit)


# ---------------------------------------------------------------------------
# subprocess helper for changed-files check
# ---------------------------------------------------------------------------


def subprocess_check(root: Path, item_id: str, sha: str) -> list[str]:
    """Return list of changed file paths for a given commit SHA."""
    rel = f"test/{item_id}.md"
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "show",
            "--name-only",
            "--format=",
            sha,
            "--",
            rel,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
