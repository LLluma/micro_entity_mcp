from pathlib import Path

from micro_entity.markdown_store import MarkdownStore
from servers.todo import _next_id, _next_order


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
