"""Tests for MarkdownStore.clear."""

from pathlib import Path


class TestClear:
    """Tests for MarkdownStore.clear."""

    def test_clear_removes_all_records(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("a", attributes={})
        store.create("b", attributes={})
        store.create("c", attributes={})

        store.clear()

        assert (tmp_path / "a.md").is_file() is False
        assert (tmp_path / "b.md").is_file() is False
        assert (tmp_path / "c.md").is_file() is False
        assert tmp_path.is_dir()
        entities, errors = store.load_all()
        assert entities == []
        assert errors == []

    def test_clear_empty_partition_is_noop(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.clear()  # should not raise

    def test_clear_leaves_non_md_files_and_subdirs(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("record", attributes={})
        (tmp_path / "keep.txt").write_text("not a record\n", encoding="utf-8")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "inside.md").write_text("should stay\n", encoding="utf-8")

        store.clear()

        assert (tmp_path / "record.md").is_file() is False
        assert tmp_path / "keep.txt"
        assert (subdir / "inside.md").read_text(encoding="utf-8") == "should stay\n"
        assert subdir.is_dir()
