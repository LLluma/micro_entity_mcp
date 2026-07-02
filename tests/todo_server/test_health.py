# pyright: reportOptionalSubscript=false, reportOperatorIssue=false, reportOptionalMemberAccess=false
import asyncio
from pathlib import Path
from typing import cast as _tc

from servers.todo import STATUS_VALUES
from tests.todo_server.conftest import _client


def test_health_returns_ok(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    assert (_tc(dict, r.structured_content))["status"] == "ok"


def test_health_reports_status_values(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    assert set((_tc(dict, r.structured_content))["status_values"]) == STATUS_VALUES


def test_status_values_constant() -> None:
    assert {"todo", "in-progress", "done", "blocked"} == STATUS_VALUES


def test_health_returns_base_segment_dir(tmp_path: Path) -> None:
    """Health reports base directory, default segment, and resolved dir."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    h = r.structured_content

    # base is a non-empty string
    assert isinstance(h["base"], str) and len(h["base"]) > 0

    # segment matches the provider's default segment ("test" in fixtures)
    assert h["segment"] == "test"

    # dir is a non-empty string that ends with the segment
    assert isinstance(h["dir"], str) and len(h["dir"]) > 0
    assert h["dir"].endswith("test")
