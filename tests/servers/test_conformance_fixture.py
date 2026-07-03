import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.servers.conftest import ConformanceCase


def test_health_ok(conformance_case: ConformanceCase, tmp_path: Path) -> None:
    async def go():
        async with conformance_case.client as c:
            return await c.call_tool("health", {})

    r = asyncio.run(go())
    d = _tc(dict, r.structured_content)
    assert d["status"] == "ok"
    assert d["status_values"] == conformance_case.status_values


def test_create_returns_expected_id(conformance_case: ConformanceCase, tmp_path: Path) -> None:
    async def go():
        async with conformance_case.client as c:
            return await c.call_tool("create", conformance_case.create_payload)

    r = asyncio.run(go())
    sc = _tc(dict, r.structured_content)
    assert set(sc.keys()) == {"item", "commit"}
    item = _tc(dict, sc["item"])
    assert item["id"] == conformance_case.expected_id
    commit = sc["commit"]
    assert isinstance(commit, str)
    assert commit  # non-empty
