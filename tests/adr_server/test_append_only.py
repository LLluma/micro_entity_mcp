import asyncio
from pathlib import Path

from tests.adr_server.conftest import _client


def test_adr_server_has_no_delete_or_clear_tools(tmp_path: Path) -> None:
    """ADR profile is append-only — no delete or clear tool must exist."""

    async def go():
        async with _client(tmp_path) as c:
            tools = await c.list_tools()
            return [t.name for t in tools]

    names = asyncio.run(go())

    assert "delete" not in names, "delete tool must not be exposed by adr server"
    assert "clear" not in names, "clear tool must not be exposed by adr server"
