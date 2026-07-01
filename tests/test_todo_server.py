"""Tests for the todo profile server (src/servers/todo.py)."""

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.markdown_store import MarkdownStore
from servers.todo import STATUS_VALUES, build_server


def _client(tmp_path: Path) -> Client:
    return Client(build_server(MarkdownStore(tmp_path)))


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
    assert {"todo", "in-progress", "done", "blocked"} == STATUS_VALUES


# ---------------------------------------------------------------------------
# _next_id unit tests
# ---------------------------------------------------------------------------

from servers.todo import _next_id, _next_order  # noqa: E402


def test_next_id_empty_partition(tmp_path: Path) -> None:
    """Empty store → "0001"."""
    store = MarkdownStore(tmp_path)
    assert _next_id(store) == "0001"


def test_next_id_after_sequential(tmp_path: Path) -> None:
    """After 0001, 0002 → next is 0003."""
    store = MarkdownStore(tmp_path)
    store.create("0001", attributes={})
    store.create("0002", attributes={})
    assert _next_id(store) == "0003"


def test_next_id_padding_width_4(tmp_path: Path) -> None:
    """With only 0001 present, next is 0002 (4 chars)."""
    store = MarkdownStore(tmp_path)
    store.create("0001", attributes={})
    assert _next_id(store) == "0002"
    assert len(_next_id(store)) == 4


def test_next_id_ignores_non_integer_stems(tmp_path: Path) -> None:
    """Non-integer stems (e.g. 'abc') are skipped; only pure int strings count."""
    store = MarkdownStore(tmp_path)
    store.create("abc", attributes={})
    store.create("0005", attributes={})
    assert _next_id(store) == "0006"


# ---------------------------------------------------------------------------
# _next_order unit tests
# ---------------------------------------------------------------------------


def test_next_order_empty_store(tmp_path: Path) -> None:
    """No entities → returns 1."""
    store = MarkdownStore(tmp_path)
    assert _next_order(store) == 1


def test_next_order_mixed_types(tmp_path: Path) -> None:
    """Bools are excluded; only int orders count."""
    store = MarkdownStore(tmp_path)
    store.create("0001", attributes={"order": True})
    store.create("0002", attributes={"order": 5})
    assert _next_order(store) == 6


# ---------------------------------------------------------------------------
# create tool tests
# ---------------------------------------------------------------------------


def test_create_defaults_status_and_order(tmp_path: Path) -> None:
    """Create with body: status==\"todo\", order==1, fresh id, body echoed."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("create", {"body": "buy milk", "attributes": {}})

    r = asyncio.run(go())
    data = r.data
    assert data["attributes"]["status"] == "todo"
    assert data["attributes"]["order"] == 1
    assert data["body"] == "buy milk"


def test_create_order_increments(tmp_path: Path) -> None:
    """Creating twice: second item gets order==2 and larger id."""

    async def go():
        async with _client(tmp_path) as c:
            first = await c.call_tool("create", {"body": "first", "attributes": {}})
            second = await c.call_tool("create", {"body": "second", "attributes": {}})
        return first.data, second.data

    first, second = asyncio.run(go())
    assert first["attributes"]["order"] == 1
    assert second["attributes"]["order"] == 2
    assert second["id"] > first["id"]


def test_create_honours_custom_status(tmp_path: Path) -> None:
    """Passing attributes={\"status\": \"in-progress\"} is honored."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "wip item", "attributes": {"status": "in-progress"}},
            )

    r = asyncio.run(go())
    assert r.data["attributes"]["status"] == "in-progress"


def test_create_rejects_bogus_status(tmp_path: Path) -> None:
    """Passing attributes={\"status\": \"bogus\"} raises a tool error."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "bad status", "attributes": {"status": "bogus"}},
            )

    with pytest.raises(ToolError):
        asyncio.run(go())


def test_create_rejects_reserved_created_attribute(tmp_path: Path) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "bad", "attributes": {"created": "x"}},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


@pytest.mark.parametrize("reserved_key", ["updated", "id"])
def test_create_rejects_other_reserved_attributes(tmp_path: Path, reserved_key: str) -> None:
    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool(
                "create",
                {"body": "bad", "attributes": {reserved_key: "x"}},
                raise_on_error=False,
            )

    r = asyncio.run(go())
    assert r.is_error is True


# ---------------------------------------------------------------------------
# get tool tests
# ---------------------------------------------------------------------------


def test_get_returns_created_entity(tmp_path: Path) -> None:
    """Create an item, then get by id: id and body must match."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "get test item", "attributes": {}})
            entity_id = created.data["id"]
            result = await c.call_tool("get", {"id": entity_id})
            return result.data

    data = asyncio.run(go())
    assert data["id"] == "0001"
    assert data["body"] == "get test item"


def test_get_missing_id_raises_tool_error(tmp_path: Path) -> None:
    """Calling get with a non-existent id raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": "9999"})

    with pytest.raises(ToolError):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# list tool tests
# ---------------------------------------------------------------------------


def test_list_empty_partition(tmp_path: Path) -> None:
    """Empty partition → list returns both items and errors empty."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert r.data["items"] == []
    assert r.data["errors"] == []


def test_list_after_creating_two_items(tmp_path: Path) -> None:
    """After two create calls, list returns both in items, errors empty."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "first", "attributes": {}})
            await c.call_tool("create", {"body": "second", "attributes": {}})
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 2
    assert r.data["errors"] == []


def test_list_scales_malformed_files_as_errors(tmp_path: Path) -> None:
    """A malformed .md file appears in errors, not as a failure."""
    store = MarkdownStore(tmp_path)
    (tmp_path / "bad.md").write_text("not a valid document\n")

    async def go():
        async with Client(build_server(store)) as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    assert len(r.data["errors"]) == 1
    assert r.data["errors"][0]["id"] == "bad"


# ---------------------------------------------------------------------------
# update tool tests
# ---------------------------------------------------------------------------


def test_update_status_transition_persists(tmp_path: Path) -> None:
    """Create an item, update its status to \"in-progress\", assert change."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "update status test", "attributes": {}},
            )
            item_id = created.data["id"]
            updated = await c.call_tool("update", {"id": item_id, "status": "in-progress"})
            return created.data, updated.data

    created, updated = asyncio.run(go())
    assert created["attributes"]["status"] == "todo"
    assert updated["attributes"]["status"] == "in-progress"


def test_update_status_invalid_raises(tmp_path: Path) -> None:
    """Invalid status string raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "bad status", "attributes": {}},
            )
            return await c.call_tool("update", {"id": created.data["id"], "status": "bogus"})

    with pytest.raises(ToolError):
        asyncio.run(go())


def test_update_order_change_persists(tmp_path: Path) -> None:
    """Update order to 5, assert returned and get'd order == 5."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "order test", "attributes": {}},
            )
            item_id = created.data["id"]
            updated = await c.call_tool("update", {"id": item_id, "order": 5})
            fetched = await c.call_tool("get", {"id": item_id})
            return updated.data, fetched.data

    updated, fetched = asyncio.run(go())
    assert updated["attributes"]["order"] == 5
    assert fetched["attributes"]["order"] == 5


def test_update_missing_id_raises(tmp_path: Path) -> None:
    """Update a non-existent id raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("update", {"id": "9999", "status": "done"})

    with pytest.raises(ToolError):
        asyncio.run(go())


def test_update_unspecified_fields_unchanged(tmp_path: Path) -> None:
    """Update only order body and status remain unchanged in returned/get'd entity."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool(
                "create",
                {"body": "original body", "attributes": {"status": "done"}},
            )
            item_id = created.data["id"]
            original_body = created.data["body"]
            original_status = created.data["attributes"]["status"]
            updated = await c.call_tool("update", {"id": item_id, "order": 99})
            fetched = await c.call_tool("get", {"id": item_id})
            return updated.data, fetched.data, original_body, original_status

    updated, fetched, original_body, original_status = asyncio.run(go())

    # Changed field
    assert updated["attributes"]["order"] == 99
    assert fetched["attributes"]["order"] == 99

    # Unchanged fields in both update return and get'd entity
    assert updated["body"] == original_body
    assert updated["attributes"]["status"] == original_status
    assert fetched["body"] == original_body
    assert fetched["attributes"]["status"] == original_status


# ---------------------------------------------------------------------------
# delete tool tests
# ---------------------------------------------------------------------------


def test_delete_removes_item(tmp_path: Path) -> None:
    """Create an item, delete it (assert returned {"deleted": <id>}),
    then get on that id raises ToolError (item is gone)."""

    async def go():
        async with _client(tmp_path) as c:
            created = await c.call_tool("create", {"body": "deleteme", "attributes": {}})
            item_id = created.data["id"]
            deleted = await c.call_tool("delete", {"id": item_id})
            return deleted.data, item_id

    deleted_data, item_id = asyncio.run(go())
    assert deleted_data == {"deleted": item_id}

    # After deletion, get should raise ToolError
    async def get_after():
        async with _client(tmp_path) as c:
            return await c.call_tool("get", {"id": item_id})

    with pytest.raises(ToolError):
        asyncio.run(get_after())


def test_delete_missing_id_raises_tool_error(tmp_path: Path) -> None:
    """Deleting a non-existent id raises ToolError."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("delete", {"id": "9999"})

    with pytest.raises(ToolError):
        asyncio.run(go())


# ---------------------------------------------------------------------------
# clear tool tests
# ---------------------------------------------------------------------------


def test_clear_empty_partition(tmp_path: Path) -> None:
    """Create two items, call clear (assert returned {"cleared": True}),
    then list returns items == []."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "first", "attributes": {}})
            await c.call_tool("create", {"body": "second", "attributes": {}})
            cleared = await c.call_tool("clear", {})
            listed = await c.call_tool("list", {})
            return cleared.data, listed.data["items"]

    cleared_data, items = asyncio.run(go())
    assert cleared_data == {"cleared": True}
    assert items == []


# ---------------------------------------------------------------------------
# next tool tests
# ---------------------------------------------------------------------------


def test_next_returns_lowest_order_actionable(tmp_path: Path) -> None:
    """Two items with orders 1 and 2, both status=todo: next returns order-1 item."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "item one", "attributes": {"status": "todo"}},
            )
            await c.call_tool("create", {"body": "item two", "attributes": {"status": "todo"}})
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data["attributes"]["order"] == 1
    assert r.data["body"] == "item one"


def test_next_skips_done_and_blocked(tmp_path: Path) -> None:
    """Item 1=done, item 2=blocked, item 3=todo: next returns item 3."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "done item", "attributes": {"status": "todo"}})
            await c.call_tool("create", {"body": "blocked item", "attributes": {"status": "todo"}})
            await c.call_tool("create", {"body": "todo item", "attributes": {"status": "todo"}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            await c.call_tool("update", {"id": "0002", "status": "blocked"})
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data["attributes"]["order"] == 3
    assert r.data["id"] == "0003"


def test_next_empty_partition_returns_none(tmp_path: Path) -> None:
    """No actionable entities → data is None."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data is None


def test_next_all_done_returns_none(tmp_path: Path) -> None:
    """One item, updated to done → next returns None."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "done item", "attributes": {"status": "todo"}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            return await c.call_tool("next", {})

    r = asyncio.run(go())
    assert r.data is None


# ---------------------------------------------------------------------------
# is_complete tool tests
# ---------------------------------------------------------------------------


def test_is_complete_all_done(tmp_path: Path) -> None:
    """Create an item, update to done → is_complete returns True."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "done item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "done"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data is True


def test_is_complete_any_todo(tmp_path: Path) -> None:
    """Default create gives status todo → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "todo item", "attributes": {}})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data is False


def test_is_complete_any_in_progress(tmp_path: Path) -> None:
    """Item with status in-progress → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "wip item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "in-progress"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data is False


def test_is_complete_any_blocked(tmp_path: Path) -> None:
    """Item with status blocked → is_complete returns False."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "blocked item", "attributes": {}})
            await c.call_tool("update", {"id": "0001", "status": "blocked"})
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data is False


def test_is_complete_empty_partition(tmp_path: Path) -> None:
    """No items at all → vacuous True."""

    async def go():
        async with _client(tmp_path) as c:
            return await c.call_tool("is_complete", {})

    r = asyncio.run(go())
    assert r.data is True


# ---------------------------------------------------------------------------
# query tool tests
# ---------------------------------------------------------------------------


def test_query_filter_by_status(tmp_path: Path) -> None:
    """Create three items; update one to blocked;
    query({"status": ["blocked"]}) returns only that one."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "item one", "attributes": {}})
            await c.call_tool("create", {"body": "item two", "attributes": {}})
            await c.call_tool("create", {"body": "item three", "attributes": {}})
            await c.call_tool("update", {"id": "0002", "status": "blocked"})
            return await c.call_tool("query", {"criteria": {"status": ["blocked"]}})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 1
    assert r.data["items"][0]["attributes"]["status"] == "blocked"


def test_query_empty_criteria_returns_all(tmp_path: Path) -> None:
    """query({}) (no args) returns ALL items."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "one", "attributes": {}})
            await c.call_tool("create", {"body": "two", "attributes": {}})
            await c.call_tool("create", {"body": "three", "attributes": {}})
            r1 = await c.call_tool("query", {"criteria": {}})
            r2 = await c.call_tool("query", {})
            return r1.data["items"], r2.data["items"]

    all_items, no_args_items = asyncio.run(go())
    assert len(all_items) == 3
    assert len(no_args_items) == 3


def test_query_no_matches_returns_empty(tmp_path: Path) -> None:
    """query({"status": ["nonexistent-status"]}) → items == []."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool("create", {"body": "one", "attributes": {}})
            return await c.call_tool("query", {"criteria": {"status": ["nonexistent-status"]}})

    r = asyncio.run(go())
    assert r.data["items"] == []


def test_query_membership_or_within_key(tmp_path: Path) -> None:
    """Create items with status todo and done;
    query({"status": ["todo", "done"]}) returns both."""

    async def go():
        async with _client(tmp_path) as c:
            await c.call_tool(
                "create",
                {"body": "todo item", "attributes": {"status": "todo"}},
            )
            await c.call_tool(
                "create",
                {"body": "done item", "attributes": {"status": "done"}},
            )
            return await c.call_tool("query", {"criteria": {"status": ["todo", "done"]}})

    r = asyncio.run(go())
    assert len(r.data["items"]) == 2
