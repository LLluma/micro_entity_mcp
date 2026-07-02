"""Tests for the project/segment override on every DATA tool."""

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.partition import StoreProvider
from servers.todo import build_server

# ---------------------------------------------------------------------------
# Test 1: default segment works — project arg omitted
# ---------------------------------------------------------------------------


def test_default_segment_create_and_list(tmp_path: Path) -> None:
    """Provider with default segment 'proj' — create (no project arg) writes
    under tmp_path/proj/ and list returns the item."""

    async def go():
        provider = StoreProvider(tmp_path, "proj")
        async with Client(build_server(provider)) as c:
            await c.call_tool("create", {"body": "default item", "attributes": {}})
            result = await c.call_tool("list", {"include_body": True})
        return result

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["body"] == "default item"
    # Verify file actually under tmp_path/proj/
    assert (tmp_path / "proj" / "0001.md").exists()


# ---------------------------------------------------------------------------
# Test 2: project override writes to different segment — isolation
# ---------------------------------------------------------------------------


def test_project_override_isolation(tmp_path: Path) -> None:
    """create with project='other' writes under tmp_path/other/;
    default list (segment 'proj') does NOT see it, and
    list with project='other' DOES."""

    async def go():
        provider = StoreProvider(tmp_path, "proj")
        async with Client(build_server(provider)) as c:
            # Create in default segment (proj)
            await c.call_tool("create", {"body": "proj item", "attributes": {}})
            # Create in 'other' segment
            await c.call_tool(
                "create",
                {"body": "other item", "attributes": {}, "project": "other"},
            )
            # Default list (proj) should see only the default item
            list_default = await c.call_tool("list", {"include_body": True})
            # List with project='other' should see only the other item
            list_other = await c.call_tool("list", {"project": "other", "include_body": True})
        return list_default, list_other

    default_result, other_result = asyncio.run(go())
    assert len(default_result.data["items"]) == 1
    assert default_result.data["items"][0]["body"] == "proj item"
    assert len(other_result.data["items"]) == 1
    assert other_result.data["items"][0]["body"] == "other item"
    # File locations
    assert (tmp_path / "proj" / "0001.md").exists()
    assert (tmp_path / "other" / "0001.md").exists()


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
    assert r.data["status"] == "ok"
    assert "status_values" in r.data
