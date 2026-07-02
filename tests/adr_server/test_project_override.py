"""Tests for the project/segment override on every DATA tool."""

import asyncio
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.partition import StoreProvider
from servers.adr import build_server

# ---------------------------------------------------------------------------
# Test 1: default segment works — project arg omitted
# ---------------------------------------------------------------------------


def test_default_segment_add_and_list(tmp_path: Path) -> None:
    """Provider with default segment 'proj' — add (no project arg) writes
    under tmp_path/proj/ and list returns the item."""

    async def go():
        provider = StoreProvider(tmp_path, "proj")
        async with Client(build_server(provider)) as c:
            await c.call_tool("create", {"title": "T", "body": "b"})
            result = await c.call_tool("list", {})
        return result

    r = asyncio.run(go())
    assert len((_tc(dict, r.structured_content))["items"]) == 1
    assert (_tc(dict, r.structured_content))["items"][0]["id"] == "ADR-0001"
    # Verify file actually under tmp_path/proj/
    assert (tmp_path / "proj" / "ADR-0001.md").exists()


# ---------------------------------------------------------------------------
# Test 2: project override writes to different segment — isolation
# ---------------------------------------------------------------------------


def test_project_override_isolation(tmp_path: Path) -> None:
    """add with project='_shared' writes under tmp_path/_shared/;
    default list (segment 'proj') does NOT see it, and
    list with project='_shared' DOES."""

    async def go():
        provider = StoreProvider(tmp_path, "proj")
        async with Client(build_server(provider)) as c:
            # Add in default segment (proj)
            await c.call_tool("create", {"title": "Proj item", "body": "body"})
            # Add in '_shared' segment
            await c.call_tool(
                "create",
                {"title": "Shared item", "body": "body", "project": "_shared"},
            )
            # Default list (proj) should see only the default item
            list_default = await c.call_tool("list", {})
            # List with project='_shared' should see only the other item
            list_shared = await c.call_tool("list", {"project": "_shared"})
        return list_default, list_shared

    default_result, shared_result = asyncio.run(go())
    assert len((_tc(dict, default_result.structured_content))["items"]) == 1
    _items = (_tc(dict, default_result.structured_content))["items"]
    assert _items[0]["attributes"]["title"] == "Proj item"
    assert len((_tc(dict, shared_result.structured_content))["items"]) == 1
    _items2 = (_tc(dict, shared_result.structured_content))["items"]
    assert _items2[0]["attributes"]["title"] == "Shared item"
    # File locations
    assert (tmp_path / "proj" / "ADR-0001.md").exists()
    assert (tmp_path / "shared" / "ADR-0001.md").exists()


# ---------------------------------------------------------------------------
# Test 3: default segment None → data tool with no project raises
# ---------------------------------------------------------------------------


def test_none_default_project_raises_tool_error(tmp_path: Path) -> None:
    """StoreProvider(tmp_path, None): calling any data tool without project raises
    a tool error."""

    async def go():
        provider = StoreProvider(tmp_path, None)
        async with Client(build_server(provider)) as c:
            return await c.call_tool("list", {})

    with pytest.raises(ToolError):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# Test 4: health still works and takes no project
# ---------------------------------------------------------------------------


def test_health_no_project_param(tmp_path: Path) -> None:
    """health() works regardless of provider default segment and takes no project."""

    async def go():
        provider = StoreProvider(tmp_path, None)
        async with Client(build_server(provider)) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["status"] == "ok"
    assert "status_values" in (_tc(dict, r.structured_content))
