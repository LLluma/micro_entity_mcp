import asyncio
from pathlib import Path

from tests.issue_server.conftest import _client

EXPECTED_TOOLS = {
    "health",
    "create",
    "get",
    "list",
    "query",
    "search",
    "update",
    "patch_body",
    "history",
    "diff",
    "revert",
    "delete",
}
FORBIDDEN_TOOLS = {"next", "is_complete", "supersede"}


def test_tool_surface_has_expected_tools(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        return {t.name for t in tools}

    tool_names = asyncio.run(go())
    for name in EXPECTED_TOOLS:
        assert name in tool_names, f"Expected tool '{name}' not found"


def test_tool_surface_no_forbidden_tools(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
        return {t.name for t in tools}

    tool_names = asyncio.run(go())
    for name in FORBIDDEN_TOOLS:
        assert name not in tool_names, f"Forbidden tool '{name}' must not be present"
