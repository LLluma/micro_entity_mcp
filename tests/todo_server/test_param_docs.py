"""Verify that Annotated Field descriptions surface in advertised inputSchema."""

import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client


def test_patch_body_old(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "patch_body")
            return tool.inputSchema["properties"]["old"]["description"]

    desc = asyncio.run(go())
    assert desc == ("Literal text to match in the body; must occur exactly once.")


def test_patch_body_new(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "patch_body")
            return tool.inputSchema["properties"]["new"]["description"]

    desc = asyncio.run(go())
    assert desc == "Replacement text for the matched occurrence."


def test_query_criteria(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "query")
            return tool.inputSchema["properties"]["criteria"]["description"]

    desc = asyncio.run(go())
    assert desc == ("{key: [values]}: within-key OR, across-key AND; type-strict matching.")


def test_diff_ref(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "diff")
            return tool.inputSchema["properties"]["ref"]["description"]

    desc = asyncio.run(go())
    assert desc == ("Git ref or sha; with no refs, shows the last change to the file.")


def test_diff_to(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "diff")
            return tool.inputSchema["properties"]["to"]["description"]

    desc = asyncio.run(go())
    assert desc == ("Optional second git ref; diff is ref..to (else ref..working-tree).")


def test_revert_ref(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "revert")
            return tool.inputSchema["properties"]["ref"]["description"]

    desc = asyncio.run(go())
    assert desc == "Git ref or sha to restore the entity's content from."


def test_history_limit(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "history")
            return tool.inputSchema["properties"]["limit"]["description"]

    desc = asyncio.run(go())
    assert desc == ("Maximum number of commits to return (newest first).")


def test_create_attributes(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "create")
            return tool.inputSchema["properties"]["attributes"]["description"]

    desc = asyncio.run(go())
    assert desc == ("Free-form attribute bag; reserved keys id/created/updated are rejected.")


def test_update_attributes(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            tool = next(t for t in tools if t.name == "update")
            return tool.inputSchema["properties"]["attributes"]["description"]

    desc = asyncio.run(go())
    assert desc == ("Free-form attribute bag; reserved keys id/created/updated are rejected.")
