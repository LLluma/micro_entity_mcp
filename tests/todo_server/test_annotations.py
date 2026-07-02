"""Verify MCP tool annotations surface via list_tools()."""

import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client


def _list_tools(tmp_path: Path) -> dict:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            return {t.name: t for t in tools}

    return asyncio.run(go())


def test_read_only_annotations(tmp_path: Path) -> None:
    """health, get, list, query, next, is_complete, history, diff → readOnlyHint=True."""
    by_name = _list_tools(tmp_path)

    for name in ("health", "get", "list", "query", "next", "is_complete", "history", "diff"):
        tool = by_name.get(name)
        assert tool is not None, f"{name} tool missing"
        assert tool.annotations.readOnlyHint is True, f"{name}.annotations.readOnlyHint not True"


def test_destructive_delete(tmp_path: Path) -> None:
    """delete → destructiveHint=True, idempotentHint=True."""
    by_name = _list_tools(tmp_path)
    tool = by_name["delete"]
    assert tool is not None
    assert tool.annotations.destructiveHint is True
    assert tool.annotations.idempotentHint is True


def test_destructive_create(tmp_path: Path) -> None:
    """create → destructiveHint=False."""
    by_name = _list_tools(tmp_path)
    tool = by_name["create"]
    assert tool is not None
    assert tool.annotations.destructiveHint is False


def test_idempotent_update(tmp_path: Path) -> None:
    """update → idempotentHint=True, destructiveHint=False."""
    by_name = _list_tools(tmp_path)
    tool = by_name["update"]
    assert tool is not None
    assert tool.annotations.idempotentHint is True
    assert tool.annotations.destructiveHint is False


def test_destructive_false_tools(tmp_path: Path) -> None:
    """patch_body and revert → destructiveHint=False."""
    by_name = _list_tools(tmp_path)

    for name in ("patch_body", "revert"):
        tool = by_name[name]
        assert tool is not None
        assert tool.annotations.destructiveHint is False
