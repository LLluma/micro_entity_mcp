"""Tests for MarkdownStore."""

from pathlib import Path

import pytest


class TestPathFor:
    """Tests for MarkdownStore._path_for."""

    def test_path_for_resolves_id_to_md_file(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        result = store._path_for("ADR-0007")
        assert result == tmp_path / "ADR-0007.md"

    def test_path_for_rejects_invalid_id(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.validation import FormError

        store = MarkdownStore(tmp_path)
        with pytest.raises(FormError):
            store._path_for("../etc/passwd")
        with pytest.raises(FormError):
            store._path_for("A" * 201)
        with pytest.raises(FormError):
            store._path_for("")

    def test_init_creates_missing_directory(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        missing = tmp_path / "sub" / "nested"
        assert not missing.exists()
        MarkdownStore(missing)
        assert missing.is_dir()

    def test_path_for_stays_inside_directory(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.validation import FormError

        # Even a syntactically valid id that contains ``..`` must resolve
        # inside the store directory.
        store = MarkdownStore(tmp_path)
        with pytest.raises(FormError):
            store._path_for("..")
        with pytest.raises(FormError):
            store._path_for("sub/../../etc")
