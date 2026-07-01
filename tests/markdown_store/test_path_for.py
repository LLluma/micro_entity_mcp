"""Tests for MarkdownStore._path_for and exists."""

from pathlib import Path

import pytest


class TestPathFor:
    """Tests for MarkdownStore._path_for."""

    def test_path_for_resolves_id_to_md_file(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        result = store.path_for("ADR-0007")
        assert result == tmp_path / "ADR-0007.md"

    def test_path_for_rejects_invalid_id(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.validation import FormError

        store = MarkdownStore(tmp_path)
        with pytest.raises(FormError):
            store.path_for("../etc/passwd")
        with pytest.raises(FormError):
            store.path_for("A" * 201)
        with pytest.raises(FormError):
            store.path_for("")


class TestExists:
    """Tests for MarkdownStore.exists."""

    def test_exists_returns_true_for_existing_record(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        store.create("present", attributes={})

        assert store.exists("present") is True

    def test_exists_returns_false_for_missing_record(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        assert store.exists("missing") is False

    def test_init_creates_missing_directory(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        missing = tmp_path / "sub" / "nested"
        assert not missing.exists()
        MarkdownStore(missing)
        assert missing.is_dir()
