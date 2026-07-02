import asyncio
from pathlib import Path

from tests.todo_server.conftest import _client


def test_no_clear_tool_registered(tmp_path: Path) -> None:
    """The todo server had its `clear` tool removed; assert it is absent."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            return [t.name for t in tools]

    names = asyncio.run(go())
    assert "clear" not in names
