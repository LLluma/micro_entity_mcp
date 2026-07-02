"""Tests for ``_next_adr_id``.

The helper scans the store for existing ``ADR-NNNN`` ids, finds the maximum,
and returns the next one.
"""

from pathlib import Path

from micro_entity.markdown_store import MarkdownStore
from servers.adr import _next_adr_id


def test_empty_store(tmp_path: Path) -> None:
    """No records → first id is ADR-0001."""
    store = MarkdownStore(tmp_path)
    result = _next_adr_id(store)
    assert result == "ADR-0001"


def test_single_record_adr_0001(tmp_path: Path) -> None:
    """One record at ADR-0001 → next is ADR-0002."""
    store = MarkdownStore(tmp_path)
    store.create(
        "ADR-0001",
        attributes={"title": "First"},
        body="decide something",
    )
    result = _next_adr_id(store)
    assert result == "ADR-0002"


def test_gap_returns_max_plus_one(tmp_path: Path) -> None:
    """ADR-0001 and ADR-0005 → max is 5, next is ADR-0006."""
    store = MarkdownStore(tmp_path)
    store.create("ADR-0001", attributes={"title": "First"}, body="b")
    store.create("ADR-0005", attributes={"title": "Fifth"}, body="b")
    result = _next_adr_id(store)
    assert result == "ADR-0006"


def test_non_matching_stems_ignored(tmp_path: Path) -> None:
    """ADR-SHA1, foo, ADR-0002 → only ADR-0002 counts → ADR-0003."""
    store = MarkdownStore(tmp_path)
    store.create("ADR-0002", attributes={"title": "Valid"}, body="b")
    store.create("ADR-SHA1", attributes={"title": "Sha"}, body="b")
    store.create("foo", attributes={"title": "Foobar"}, body="b")
    result = _next_adr_id(store)
    assert result == "ADR-0003"


def test_width_grows(tmp_path: Path) -> None:
    """ADR-10000 → ADR-10001 (format width grows beyond 4 digits)."""
    store = MarkdownStore(tmp_path)
    store.create("ADR-10000", attributes={"title": "Big"}, body="b")
    result = _next_adr_id(store)
    assert result == "ADR-10001"
