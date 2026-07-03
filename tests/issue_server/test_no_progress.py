import asyncio
from pathlib import Path
from typing import cast as _tc

from tests.issue_server.conftest import _client


def test_issue_update_has_no_progress(tmp_path: Path) -> None:
    """Issue update returns {ok, id, commit} only — no progress key."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"title": "T", "body": "b"})
            result = await c.call_tool(
                "update",
                {"id": "ISSUE-0001", "status": "closed"},
            )
        return _tc(dict, result.structured_content)

    data = asyncio.run(go())
    assert "progress" not in data
