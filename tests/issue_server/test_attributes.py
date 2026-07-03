import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.issue_server.conftest import _client


def test_create_stores_freeform_attributes_verbatim(tmp_path: Path) -> None:
    attrs = {
        "external_refs": ["github#123", "jira:PROJ-45"],
        "relates_to": ["ADR-0007"],
        "resolved_by": ["abc123", "ADR-0009"],
        "duplicate_of": "ISSUE-0001",
    }

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {
                    "title": "Feature request",
                    "body": "needs tracking",
                    "attributes": attrs,
                },
            )
            result = await c.call_tool("get", {"id": "ISSUE-0001"})
        data = (_tc(dict, result.structured_content))["item"]
        stored = data["attributes"]
        assert stored["external_refs"] == ["github#123", "jira:PROJ-45"]
        assert stored["relates_to"] == ["ADR-0007"]
        assert stored["resolved_by"] == ["abc123", "ADR-0009"]
        assert stored["duplicate_of"] == "ISSUE-0001"

    asyncio.run(go())
