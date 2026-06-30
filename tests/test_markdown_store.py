"""Tests for MarkdownStore."""

from pathlib import Path

import pytest


class TestAtomicWrite:
    """Tests for MarkdownStore._atomic_write."""

    def test_atomic_write_creates_file_with_exact_content(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        target = tmp_path / "record.md"
        store._atomic_write(target, "hello world\n")
        assert target.read_text(encoding="utf-8") == "hello world\n"

    def test_atomic_write_unicode_and_trailing_newline(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        target = tmp_path / "unicode.md"
        text = "naïve café 日本語 🌍\n"
        store._atomic_write(target, text)
        assert target.read_text(encoding="utf-8") == text

    def test_atomic_write_overwrites_atomically_no_temp_left(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        target = tmp_path / "swap.md"

        store._atomic_write(target, "first\n")
        assert target.read_text(encoding="utf-8") == "first\n"

        store._atomic_write(target, "second\n")
        assert target.read_text(encoding="utf-8") == "second\n"

        # No temp/* files should be left behind matching our pattern
        temp_files = list(tmp_path.glob(".*.tmp.*"))
        assert len(temp_files) == 0


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
