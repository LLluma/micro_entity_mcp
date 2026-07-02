"""Verify MCP tool annotations surface through list_tools() in ADR server."""

from pathlib import Path

import anyio
from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.adr import build_server


def _client(tmp_path: Path) -> Client:
    return Client(build_server(StoreProvider(tmp_path, "seg")))


def test_readonly_annotations(tmp_path: Path) -> None:  # pyright: ignore[reportOptionalMemberAccess]
    """readOnlyHint: True on get, search, diff."""

    async def _run() -> None:
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool_map = {t.name: t for t in tools}  # type: ignore[var-annotated]

        for name in ("get", "search", "diff"):
            tool = tool_map[name]
            ann = tool.annotations
            assert ann is not None
            assert ann.readOnlyHint is True

    anyio.run(_run)


def test_supersede_destructive(tmp_path: Path) -> None:  # pyright: ignore[reportOptionalMemberAccess]
    """supersede is destructive."""

    async def _run() -> None:
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        tool_map = {t.name: t for t in tools}

        tool = tool_map["supersede"]
        ann = tool.annotations
        assert ann is not None
        assert ann.destructiveHint is True

    anyio.run(_run)


def test_create_non_destructive(tmp_path: Path) -> None:  # pyright: ignore[reportOptionalMemberAccess]
    """create is not destructive."""

    async def _run() -> None:
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        tool_map = {t.name: t for t in tools}

        tool = tool_map["create"]
        ann = tool.annotations
        assert ann is not None
        assert ann.destructiveHint is False

    anyio.run(_run)


def test_update_idempotent(tmp_path: Path) -> None:  # pyright: ignore[reportOptionalMemberAccess]
    """update.idempotentHint is True."""

    async def _run() -> None:
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        tool_map = {t.name: t for t in tools}

        tool = tool_map["update"]
        ann = tool.annotations
        assert ann is not None
        assert ann.idempotentHint is True

    anyio.run(_run)


def test_patch_body_idempotent(tmp_path: Path) -> None:  # pyright: ignore[reportOptionalMemberAccess]
    """patch_body.idempotentHint is True."""

    async def _run() -> None:
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        tool_map = {t.name: t for t in tools}

        tool = tool_map["patch_body"]
        ann = tool.annotations
        assert ann is not None
        assert ann.idempotentHint is True

    anyio.run(_run)


def test_commit_message_description(tmp_path: Path) -> None:
    """commit's message param has a non-empty description in its inputSchema."""

    async def _run() -> None:
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        tool_map = {t.name: t for t in tools}

        msg_desc = tool_map["commit"].inputSchema["properties"]["message"]["description"]
        assert isinstance(msg_desc, str) and len(msg_desc) > 0, (
            f"commit.message description expected non-empty string, got: {msg_desc!r}"
        )

    anyio.run(_run)
