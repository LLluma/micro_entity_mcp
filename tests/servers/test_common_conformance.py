import asyncio
from typing import cast as _tc

import pytest
from fastmcp.exceptions import ToolError

from tests.servers.conftest import ConformanceCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed(case: ConformanceCase):
    """Create one entity and return the async runner wrapper."""

    async def go():
        async with case.client as c:
            return await c.call_tool("create", case.create_payload)

    return go


# ---------------------------------------------------------------------------
# 1. test_list_bodyless_default_and_include_body
# ---------------------------------------------------------------------------


def test_list_bodyless_default_and_include_body(
    conformance_case: ConformanceCase,
) -> None:
    r = _seed(conformance_case)()
    asyncio.run(r)

    # default (no include_body) → no body key
    async def bodyless():
        async with conformance_case.client as c:
            result = await c.call_tool("list", {})
            return result

    r_list = asyncio.run(bodyless())
    items = _tc(dict, r_list.structured_content)["items"]
    assert any(i["id"] == conformance_case.expected_id for i in items)
    for item in items:
        assert "body" not in item

    # include_body=True → body key present
    async def with_body():
        async with conformance_case.client as c:
            result = await c.call_tool("list", {"include_body": True})
            return result

    r_with = asyncio.run(with_body())
    items_with = _tc(dict, r_with.structured_content)["items"]
    for item in items_with:
        if item["id"] == conformance_case.expected_id:
            assert "body" in item
            assert item["body"] == "hello world"


# ---------------------------------------------------------------------------
# 2. test_search_bodyless_default_and_include_body
# ---------------------------------------------------------------------------


def test_search_bodyless_default_and_include_body(
    conformance_case: ConformanceCase,
) -> None:
    asyncio.run(_seed(conformance_case)())

    async def bodyless():
        async with conformance_case.client as c:
            result = await c.call_tool("search", {"text": "hello"})
            return result

    r_search = asyncio.run(bodyless())
    items = _tc(dict, r_search.structured_content)["items"]
    assert len(items) >= 1
    for item in items:
        assert "body" not in item

    async def with_body():
        async with conformance_case.client as c:
            result = await c.call_tool("search", {"text": "hello", "include_body": True})
            return result

    r_with = asyncio.run(with_body())
    items_with = _tc(dict, r_with.structured_content)["items"]
    assert len(items_with) >= 1
    for item in items_with:
        if item["id"] == conformance_case.expected_id:
            assert "body" in item
            assert item["body"] == "hello world"


# ---------------------------------------------------------------------------
# 3. test_id_normalization_resolves_to_canonical
# ---------------------------------------------------------------------------


def test_id_normalization_resolves_to_canonical(
    conformance_case: ConformanceCase,
) -> None:
    asyncio.run(_seed(conformance_case)())

    async def go():
        async with conformance_case.client as c:
            result = await c.call_tool("get", {"id": conformance_case.denormalized_id})
            return result

    r = asyncio.run(go())
    item = _tc(dict, r.structured_content)["item"]
    assert item["id"] == conformance_case.expected_id


# ---------------------------------------------------------------------------
# 4. test_canonical_not_found_message
# ---------------------------------------------------------------------------


def test_canonical_not_found_message(
    conformance_case: ConformanceCase,
) -> None:
    async def go():
        async with conformance_case.client as c:
            await c.call_tool("get", {"id": conformance_case.missing_id})

    with pytest.raises(ToolError, match=f"not found: {conformance_case.missing_id}"):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# 5. test_patch_body_text_not_found
# ---------------------------------------------------------------------------


def test_patch_body_text_not_found(
    conformance_case: ConformanceCase,
) -> None:
    asyncio.run(_seed(conformance_case)())

    async def go():
        async with conformance_case.client as c:
            await c.call_tool(
                "patch_body",
                {
                    "id": conformance_case.expected_id,
                    "old": "zzz-absent",
                    "new": "x",
                },
            )

    with pytest.raises(ToolError, match="patch text not found"):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# 6. test_patch_body_text_not_unique
# ---------------------------------------------------------------------------


def test_patch_body_text_not_unique(
    conformance_case: ConformanceCase,
) -> None:
    asyncio.run(_seed(conformance_case)())

    async def go():
        async with conformance_case.client as c:
            await c.call_tool(
                "patch_body",
                {
                    "id": conformance_case.expected_id,
                    "old": "o",
                    "new": "0",
                },
            )

    with pytest.raises(ToolError, match="not unique"):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# 7. test_history_returns_commits
# ---------------------------------------------------------------------------


def test_history_returns_commits(conformance_case: ConformanceCase) -> None:
    asyncio.run(_seed(conformance_case)())

    async def go():
        async with conformance_case.client as c:
            result = await c.call_tool("history", {"id": conformance_case.expected_id})
            return result

    r = asyncio.run(go())
    commits = _tc(dict, r.structured_content)["commits"]
    assert len(commits) >= 1


# ---------------------------------------------------------------------------
# 8. test_diff_returns_nonempty
# ---------------------------------------------------------------------------


def test_diff_returns_nonempty(conformance_case: ConformanceCase) -> None:
    asyncio.run(_seed(conformance_case)())

    async def go():
        async with conformance_case.client as c:
            result = await c.call_tool("diff", {"id": conformance_case.expected_id})
            return result

    r = asyncio.run(go())
    diff_text = _tc(dict, r.structured_content)["diff"]
    assert isinstance(diff_text, str)
    assert diff_text


# ---------------------------------------------------------------------------
# 9. test_revert_returns_item_and_commit
# ---------------------------------------------------------------------------


def test_revert_returns_item_and_commit(
    conformance_case: ConformanceCase,
) -> None:
    async def go():
        async with conformance_case.client as c:
            # Create the entity (commits "hello world" as HEAD).
            create_r = await c.call_tool("create", conformance_case.create_payload)
            create_sha = _tc(dict, create_r.structured_content)["commit"]

            # Patch body → HEAD now has the patched content.
            await c.call_tool(
                "patch_body",
                {
                    "id": conformance_case.expected_id,
                    "old": "hello",
                    "new": "goodbye",
                },
            )

            # Revert to the create commit (which has the original "hello world").
            # Since the patch changed the body, restoring from the older SHA
            # produces a real diff → a real commit (not a git no-op).
            result = await c.call_tool(
                "revert", {"id": conformance_case.expected_id, "ref": create_sha}
            )
            return result

    r = asyncio.run(go())
    data = _tc(dict, r.structured_content)
    item = _tc(dict, data["item"])
    assert item["id"] == conformance_case.expected_id
    assert isinstance(data["commit"], str)
    assert data["commit"]  # non-empty


# ---------------------------------------------------------------------------
# 10. test_create_and_update_return_commit_sha
# ---------------------------------------------------------------------------


def test_create_and_update_return_commit_sha(
    conformance_case: ConformanceCase,
) -> None:
    # create returns commit
    async def do_create():
        async with conformance_case.client as c:
            return await c.call_tool("create", conformance_case.create_payload)

    r_create = asyncio.run(do_create())
    sc_create = _tc(dict, r_create.structured_content)
    commit_create = sc_create["commit"]
    assert isinstance(commit_create, str)
    assert commit_create

    # update returns commit
    async def do_update():
        async with conformance_case.client as c:
            return await c.call_tool(
                "update",
                {"id": conformance_case.expected_id, "status": conformance_case.status_values[0]},
            )

    r_update = asyncio.run(do_update())
    sc_update = _tc(dict, r_update.structured_content)
    commit_update = sc_update["commit"]
    assert isinstance(commit_update, str)
    assert commit_update
