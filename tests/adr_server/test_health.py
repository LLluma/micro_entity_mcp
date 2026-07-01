import asyncio
from pathlib import Path

from servers.adr import STATUS_VALUES
from tests.adr_server.conftest import _client


def test_health_returns_ok(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    assert r.data["status"] == "ok"


def test_health_reports_status_values(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    assert set(r.data["status_values"]) == STATUS_VALUES


def test_status_values_constant() -> None:
    assert {"Proposed", "Accepted", "Superseded"} == STATUS_VALUES
