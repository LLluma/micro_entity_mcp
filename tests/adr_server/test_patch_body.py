"""Tests for the ``patch_body`` tool on the ADR server."""

import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.partition import StoreProvider
from servers.adr import build_server
from tests.adr_server.conftest import _client

# ---------------------------------------------------------------------------
# success: single-occurrence patch
# ---------------------------------------------------------------------------


def test_patch_body_single_occurrence_replaces_and_preserves(tmp_path: Path) -> None:
    """Patching a body whose ``old`` occurs exactly once replaces that span
    and leaves the rest byte-for-byte; returns ``{"item": {...}}``."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-X01", "title": "X", "body": "before SPICE after"},
            )
            result = await c.call_tool(
                "patch_body",
                {"id": "ADR-X01", "old": "SPICE", "new": "GLORY"},
            )
        data = (_tc(dict, result.structured_content))["item"]
        assert data["body"] == "before GLORY after"
        # other attributes survive unchanged
        assert data["attributes"]["title"] == "X"

    asyncio.run(go())


def test_patch_body_preserves_frontmatter_order(tmp_path: Path) -> None:
    """Only the body changes; the frontmatter file on disk must be
    re-written through the normalize hook (date key stripped, timestamps
    derived)."""
    adr_dir = tmp_path / "store"
    adr_dir.mkdir()
    provider = StoreProvider(adr_dir, "seg")

    async def go():
        async with Client(build_server(provider)) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-X02", "title": "Order", "body": "start END end"},
            )
            result = await c.call_tool(
                "patch_body",
                {"id": "ADR-X02", "old": "END", "new": "DONE"},
            )
        data = (_tc(dict, result.structured_content))["item"]

        # body is patched
        assert data["body"] == "start DONE end"
        # no legacy ``date`` key in stored frontmatter
        fm_text = (adr_dir / "seg" / "ADR-X02.md").read_text(encoding="utf-8")
        assert "\ndate:" not in fm_text
        return data

    asyncio.run(go())


# ---------------------------------------------------------------------------
# error: old absent → "patch text not found"
# ---------------------------------------------------------------------------


def test_patch_body_old_absent_raises(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-X03", "title": "T", "body": "hello only world"},
            )
            await c.call_tool(
                "patch_body",
                {"id": "ADR-X03", "old": "MISSING", "new": "NOPE"},
            )

    with pytest.raises(ToolError, match="patch text not found"):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# error: old occurs twice → "patch text not unique"
# ---------------------------------------------------------------------------


def test_patch_body_old_twice_raises(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-X04", "title": "T", "body": "alpha alpha beta"},
            )
            await c.call_tool(
                "patch_body",
                {"id": "ADR-X04", "old": "alpha", "new": "BETA"},
            )

    with pytest.raises(ToolError, match="patch text not unique"):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# error: unknown id → "not found: <id>"
# ---------------------------------------------------------------------------


def test_patch_body_unknown_id_raises(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "patch_body",
                {"id": "ADR-NOPE", "old": "x", "new": "y"},
            )

    with pytest.raises(ToolError, match="not found: ADR-NOPE"):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# error: project selection
# ---------------------------------------------------------------------------


def test_patch_body_project_selection(tmp_path: Path) -> None:
    """patch_body respects the ``project`` (partition) argument."""

    # Create ADR in default partition
    async def create_project():
        adr_dir = tmp_path / "store"
        provider = StoreProvider(adr_dir, "projA")
        async with Client(build_server(provider)) as c:
            await c.call_tool(
                "create",
                {"id": "ADR-PJ1", "title": "P", "body": "one two three"},
            )

    asyncio.run(create_project())
    # Unknown partition → not found
    adr_dir = tmp_path / "store"
    unknown_provider = StoreProvider(adr_dir, "projB")

    async def go():
        async with Client(build_server(unknown_provider)) as c:
            await c.call_tool(
                "patch_body",
                {"id": "ADR-PJ1", "old": "one", "new": "ONE", "project": ""},
            )

    with pytest.raises(ToolError, match="not found: ADR-PJ1"):
        asyncio.run(go())
