import asyncio
import re
from pathlib import Path

from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.adr import STATUS_VALUES, build_server
from tests.adr_server.conftest import write_legacy_adrs


def test_dogfood_real_adr_files_all_load(tmp_path: Path) -> None:
    """Prove rich-shape ADR files load cleanly through the migration path."""
    seg_dir = tmp_path / "seg"

    # 1. Write 5 synthetic legacy ADRs
    written = write_legacy_adrs(seg_dir)
    copied = len(written)
    filename_stems = set(written)

    # Guard: we actually got 5
    assert copied >= 5, f"Expected >= 5 ADR files from fixtures, got {copied}"

    # 2. Build a client over a provider at tmp_path / seg
    provider = StoreProvider(tmp_path, "seg")
    client = Client(build_server(provider))

    # 3. Call the list tool
    async def go():
        async with client as c:
            return await c.call_tool("list", {})

    r = asyncio.run(go())
    data = r.data
    items = data["items"]
    errors = data["errors"]

    # 4. ZERO unexplained quarantines
    assert errors == [], f"ADR files quarantined: {errors}"

    # 5. Item count == file count
    assert len(items) == copied

    ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    # 6. Per-item assertions
    item_ids = set()
    has_tags_member = False
    for item in items:
        item_id = item["id"]
        item_ids.add(item_id)

        # id matches a copied filename stem
        assert item_id in filename_stems, f"Item id {item_id!r} does not match any copied file stem"

        # status is valid
        status = item["attributes"]["status"]
        assert status in STATUS_VALUES, f"{item_id}: unexpected status {status!r}"

        # non-empty body
        assert item.get("body"), f"{item_id}: missing body"

        # migrated created/updated as ISO-8601 strings
        created = item.get("created")
        updated = item.get("updated")
        assert created is not None and isinstance(created, str), (
            f"{item_id}: missing/invalid created"
        )
        assert updated is not None and isinstance(updated, str), (
            f"{item_id}: missing/invalid updated"
        )
        assert ISO_RE.match(created), f"{item_id}: created not ISO-8601: {created}"
        assert ISO_RE.match(updated), f"{item_id}: updated not ISO-8601: {updated}"

        # 7. Relation/attribute keys: every item has title
        assert "title" in item["attributes"], f"{item_id}: missing title"
        if "tags" in item["attributes"] and item["attributes"]["tags"]:
            has_tags_member = True

    assert has_tags_member, "No item has a tags attribute; expected at least one"
