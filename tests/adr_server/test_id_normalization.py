import asyncio
from pathlib import Path
from typing import cast as _tc

from fastmcp import Client
from fastmcp.exceptions import ToolError

from micro_entity.partition import StoreProvider
from servers.adr import _normalize_adr_id, build_server


def _test_client(tmp_path: Path) -> Client:
    """Inline helper matching the production+conftest wire-up."""
    return Client(build_server(StoreProvider(tmp_path, "seg", normalize_id=_normalize_adr_id)))


async def _create_adr(c: Client) -> dict:
    """Create an ADR, return its item dict."""
    r = await c.call_tool("create", {"title": "T", "body": "prose"})
    return _tc(dict, r.structured_content)["item"]


async def _get(c: Client, id: str) -> dict:
    """Call get tool, return item dict."""
    r = await c.call_tool("get", {"id": id})
    return _tc(dict, r.structured_content)["item"]


class TestBareDigitLookup:
    """1. Create an ADR (becomes ADR-0001), then get with id '1' returns
    the same entity with id ADR-0001 (bare-digit lookup normalizes)."""

    def test_bare_digit_get_bare_digit(self, tmp_path: Path) -> None:
        async def go():
            async with _test_client(tmp_path) as c:
                item = await _create_adr(c)
                assert item["id"] == "ADR-0001"
                # Look up with bare digit
                result = await _get(c, "1")
                assert result["id"] == "ADR-0001"
                assert result["attributes"]["title"] == "T"

        asyncio.run(go())


class TestLowercasePrefixedLookup:
    """2. get with id 'adr-1' (lowercase prefixed) also returns ADR-0001."""

    def test_lowercase_prefixed_get(self, tmp_path: Path) -> None:
        async def go():
            async with _test_client(tmp_path) as c:
                await _create_adr(c)
                result = await _get(c, "adr-1")
                assert result["id"] == "ADR-0001"

        asyncio.run(go())


class TestNotFoundCanonicalId:
    """3. get with non-existent id '7' raises error whose message contains
    'not found: ADR-0007' (canonical), NOT 'not found: 7'."""

    def test_not_found_reports_canonical_id(self, tmp_path: Path) -> None:
        async def go():
            async with _test_client(tmp_path) as c:
                await _create_adr(c)
                try:
                    await c.call_tool("get", {"id": "7"})
                    raise AssertionError("Should have raised")
                except ToolError as exc:
                    assert "not found: ADR-0007" in str(exc), (
                        f"Expected canonical id in error, got: {exc}"
                    )
                    # Make sure the raw value is NOT in the message
                    assert "not found: 7" not in str(exc)

        asyncio.run(go())


class TestUpdateNormalizedId:
    """4. update with id '1' (e.g. status change to 'Accepted') returns
    entity with id ADR-0001."""

    def test_update_with_normalized_id(self, tmp_path: Path) -> None:
        async def go():
            async with _test_client(tmp_path) as c:
                item = await _create_adr(c)
                assert item["id"] == "ADR-0001"
                # Update status using bare digit
                r = await c.call_tool(
                    "update",
                    {
                        "id": "1",
                        "status": "Accepted",
                    },
                )
                data = _tc(dict, r.structured_content)["item"]
                assert data["id"] == "ADR-0001"
                assert data["attributes"]["status"] == "Accepted"

        asyncio.run(go())
