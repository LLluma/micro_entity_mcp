"""Tests for ``register_common_tools`` registered on a FastMCP server."""

import asyncio
import subprocess
from pathlib import Path
from typing import cast as _tc

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from micro_entity.partition import StoreProvider
from servers._common import ProfileConfig, register_common_tools


def _init_repo(p: Path) -> None:
    subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(p), "config", "user.email", "t@localhost"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(p), "config", "user.name", "t"], check=True, capture_output=True
    )


def _cfg() -> ProfileConfig:
    return ProfileConfig(
        name="widget", instructions="Widget profile.", status_values={"open", "closed"}
    )


def _client(tmp_path: Path) -> Client:
    _init_repo(tmp_path)
    provider = StoreProvider(tmp_path, "seg")
    mcp = FastMCP("widget", instructions="Widget profile.")
    register_common_tools(mcp, provider, _cfg())
    return Client(mcp)


def _seed(provider: StoreProvider, tmp_path: Path) -> None:
    """Create entity 0001 and commit it so history/diff/revert work."""
    store = provider.get(None)
    store.create("0001", attributes={"status": "open", "title": "hi"}, body="hello world")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "seed"], check=True, capture_output=True
    )


def _client_with_seed(tmp_path: Path) -> Client:
    _init_repo(tmp_path)
    provider = StoreProvider(tmp_path, "seg")
    _seed(provider, tmp_path)
    mcp = FastMCP("widget", instructions="Widget profile.")
    register_common_tools(mcp, provider, _cfg())
    return Client(mcp)


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


def test_health_ok(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    d = _tc(dict, r.structured_content)
    assert d["status"] == "ok"
    assert d["status_values"] == ["closed", "open"]
    assert d["segment"] == "seg"


def test_health_reports_base_and_dir(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    d = _tc(dict, r.structured_content)
    assert d["base"] == str(tmp_path)
    assert d["dir"] is not None
    assert d["dir"].endswith("seg")


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_missing_raises(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "0002"})

    with pytest.raises(ToolError, match=r"not found: 0002"):
        asyncio.run(go())


def test_get_seeded_returns_entity(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("get", {"id": "0001"})

    r = asyncio.run(go())
    d = _tc(dict, r.structured_content)
    assert d["item"]["id"] == "0001"
    assert d["item"]["attributes"]["status"] == "open"
    assert d["item"]["body"] == "hello world"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_returns_seeded_entity(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = _tc(dict, r.structured_content)["items"]
    assert len(items) == 1
    assert items[0]["id"] == "0001"


def test_list_default_no_body(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    items = _tc(dict, r.structured_content)["items"]
    assert len(items) >= 1
    for item in items:
        assert "body" not in item


def test_list_include_body_true(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("list", {"include_body": True})

    r = asyncio.run(go())
    items = _tc(dict, r.structured_content)["items"]
    assert len(items) >= 1
    for item in items:
        assert "body" in item
        assert item["body"] == "hello world"


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


def test_query_match(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("query", {"criteria": {"status": ["open"]}})

    r = asyncio.run(go())
    items = _tc(dict, r.structured_content)["items"]
    assert len(items) == 1
    assert items[0]["id"] == "0001"


def test_query_no_match(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("query", {"criteria": {"status": ["closed"]}})

    r = asyncio.run(go())
    assert _tc(dict, r.structured_content)["items"] == []


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_finds_body_text(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("search", {"text": "hello"})

    r = asyncio.run(go())
    items = _tc(dict, r.structured_content)["items"]
    assert len(items) == 1
    assert items[0]["id"] == "0001"


def test_search_no_match(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("search", {"text": "absent"})

    r = asyncio.run(go())
    assert _tc(dict, r.structured_content)["items"] == []


# ---------------------------------------------------------------------------
# patch_body
# ---------------------------------------------------------------------------


def test_patch_body_replaces(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            result = await c.call_tool(
                "patch_body", {"id": "0001", "old": "hello", "new": "goodbye"}
            )
            return result

    r = asyncio.run(go())
    item = _tc(dict, r.structured_content)["item"]
    assert "goodbye world" in item["body"]


def test_patch_body_missing_text_raises(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool("patch_body", {"id": "0001", "old": "ZZZZNOTHERE", "new": "x"})

    with pytest.raises(ToolError, match="patch text not found"):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


def test_history_returns_commits(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("history", {"id": "0001"})

    r = asyncio.run(go())
    commits = _tc(dict, r.structured_content)["commits"]
    assert len(commits) >= 1


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def test_diff_returns_diff_string(tmp_path: Path) -> None:
    async def go():
        async with _client_with_seed(tmp_path) as c:
            return await c.call_tool("diff", {"id": "0001"})

    r = asyncio.run(go())
    diff_text = _tc(dict, r.structured_content)["diff"]
    assert isinstance(diff_text, str)
    assert diff_text  # non-empty
    assert "hello world" in diff_text


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_status_persists(tmp_path: Path) -> None:
    """Updating status to 'closed' persists; confirmed via follow-up get."""

    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool("update", {"id": "0001", "status": "closed"})
            result = await c.call_tool("get", {"id": "0001"})
            return result

    r = asyncio.run(go())
    d = _tc(dict, r.structured_content)
    assert d["item"]["attributes"]["status"] == "closed"


def test_update_invalid_explicit_status_raises(tmp_path: Path) -> None:
    """Explicit invalid status ('bogus') raises a tool error."""

    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool("update", {"id": "0001", "status": "bogus"})

    with pytest.raises(ToolError, match=r"invalid value"):
        asyncio.run(go())


def test_update_invalid_status_in_attributes_raises(tmp_path: Path) -> None:
    """Invalid status via attributes={'status': 'bogus'} raises a tool error."""

    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool("update", {"id": "0001", "attributes": {"status": "bogus"}})

    with pytest.raises(ToolError, match=r"invalid value"):
        asyncio.run(go())


def test_update_explicit_status_wins_over_attributes(tmp_path: Path) -> None:
    """explicit status='closed' wins when attributes={'status': 'open'} is also passed."""

    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool(
                "update",
                {"id": "0001", "status": "closed", "attributes": {"status": "open"}},
            )
            result = await c.call_tool("get", {"id": "0001"})
            return result

    r = asyncio.run(go())
    d = _tc(dict, r.structured_content)
    assert d["item"]["attributes"]["status"] == "closed"


def test_update_reserved_key_raises(tmp_path: Path) -> None:
    """attributes={'id': 'x'} (reserved key) raises a tool error."""

    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool("update", {"id": "0001", "attributes": {"id": "x"}})

    with pytest.raises(ToolError, match=r"cannot set reserved keys"):
        asyncio.run(go())


def test_update_missing_id_raises(tmp_path: Path) -> None:
    """Update on a missing id raises a tool error with message 'not found: 0002'."""

    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool("update", {"id": "0002"})

    with pytest.raises(ToolError, match=r"not found: 0002"):
        asyncio.run(go())


def test_update_custom_attribute_persists(tmp_path: Path) -> None:
    """Updating a custom attribute (priority=high) persists."""

    async def go():
        async with _client_with_seed(tmp_path) as c:
            await c.call_tool(
                "update",
                {"id": "0001", "attributes": {"priority": "high"}},
            )
            result = await c.call_tool("get", {"id": "0001"})
            return result

    r = asyncio.run(go())
    d = _tc(dict, r.structured_content)
    assert d["item"]["attributes"]["priority"] == "high"
    assert d["item"]["attributes"]["status"] == "open"  # preserved
