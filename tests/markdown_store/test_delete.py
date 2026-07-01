"""Tests for MarkdownStore.delete."""

from pathlib import Path

import pytest


class TestDelete:
    """Tests for MarkdownStore.delete."""

    def test_delete_removes_file(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.store import NotFoundError

        store = MarkdownStore(tmp_path)

        store.create("doc", attributes={"x": 1})
        path = tmp_path / "doc.md"
        assert path.is_file()

        store.delete("doc")

        assert not path.is_file()
        with pytest.raises(NotFoundError):
            store.get("doc")

    def test_delete_missing_id_raises_not_found_error(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.store import NotFoundError

        store = MarkdownStore(tmp_path)

        with pytest.raises(NotFoundError):
            store.delete("ghost")
