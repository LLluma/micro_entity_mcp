import asyncio
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from tests.todo_server.conftest import _client


def test_patch_body_replaces_single_occurrence(tmp_path: Path) -> None:
    """Patching a body whose old occurs exactly once replaces that span."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "hello world hello", "attributes": {}},
            )
            item_id = created.data["item"]["id"]
            patched = await c.call_tool(
                "patch_body",
                {"id": item_id, "old": "world", "new": "universe"},
            )
            return item_id, created.data, patched.data

    item_id, created, patched = asyncio.run(go())

    # Original body unchanged in creation response
    assert created["item"]["body"] == "hello world hello"
    # Patch returned the updated item
    assert patched["item"]["id"] == item_id
    assert patched["item"]["body"] == "hello universe hello"


def test_patch_body_preserves_unchanged_bytes(tmp_path: Path) -> None:
    """Only the matched span changes; all surrounding chars unchanged."""

    async def go():
        async with _client(tmp_path) as c:
            original_body = "foo__bar__baz"
            created = await c.call_tool(
                "create",
                {"body": original_body, "attributes": {}},
            )
            item_id = created.data["item"]["id"]
            patched = await c.call_tool(
                "patch_body",
                {"id": item_id, "old": "__bar__", "new": "-QUACK-"},
            )
            return patched.data["item"]["body"]

    result_body = asyncio.run(go())
    assert result_body == "foo-QUACK-baz"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_patch_body_absent_old_raises_tool_error(tmp_path: Path) -> None:
    """When old text does not appear, ToolError('patch text not found')."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "only banana", "attributes": {}},
            )
            return await c.call_tool(
                "patch_body",
                {"id": "0001", "old": "apple", "new": "orange"},
            )

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())

    assert str(exc_info.value) == "patch text not found"


def test_patch_body_duplicate_old_raises_tool_error(tmp_path: Path) -> None:
    """When old occurs more than once, ToolError('patch text not unique')."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "dup dup dup", "attributes": {}},
            )
            return await c.call_tool(
                "patch_body",
                {"id": "0001", "old": "dup", "new": "unique"},
            )

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())

    assert str(exc_info.value) == "patch text not unique"


def test_patch_body_unknown_id_raises_tool_error(tmp_path: Path) -> None:
    """Patching a non-existent id raises ToolError('not found: <id>')."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "patch_body",
                {"id": "9999", "old": "x", "new": "y"},
            )

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(go())

    assert str(exc_info.value) == "not found: 9999"
