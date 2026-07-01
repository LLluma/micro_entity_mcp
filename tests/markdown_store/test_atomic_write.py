"""Tests for MarkdownStore._atomic_write."""

from pathlib import Path


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

    def test_atomic_write_public_wrapper_writes_exact_content(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        target = store.path_for("record")
        store.atomic_write(target, "hello world\n")

        assert target.read_text(encoding="utf-8") == "hello world\n"

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
