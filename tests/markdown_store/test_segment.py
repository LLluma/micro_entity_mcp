"""Tests for MarkdownStore optional segment parameter."""

from pathlib import Path

import pytest


class TestSegmentNoFlag:
    """No segment -> directory is exactly `directory` (unchanged)."""

    def test_no_segment_resolves_to_base_directory(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        assert store._directory == tmp_path

    def test_no_segment_writes_file_flat_under_base(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        store.create("entity-a", attributes={"role": "admin"})

        assert (tmp_path / "entity-a.md").is_file()

    def test_no_segment_path_for_flat(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        assert store.path_for("entity-a") == tmp_path / "entity-a.md"


class TestSegmentProvided:
    """segment provided -> directory is `directory / segment`."""

    def test_segment_resolves_to_base_segment(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path, segment="proj")
        assert store._directory == tmp_path / "proj"

    def test_segment_creates_directory(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        segment_dir = tmp_path / "proj"
        assert not segment_dir.exists()
        MarkdownStore(tmp_path, segment="proj")
        assert segment_dir.is_dir()

    def test_segment_writes_file_under_segmented_dir(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path, segment="proj")
        store.create("entity-a", attributes={"role": "admin"})

        assert (tmp_path / "proj" / "entity-a.md").is_file()
        # NOT flat under tmp
        assert not (tmp_path / "entity-a.md").exists()

    def test_segment_path_for_under_segment(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path, segment="proj")
        assert store.path_for("entity-a") == tmp_path / "proj" / "entity-a.md"

    def test_segment_path_for_still_guarded(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.validation import FormError

        store = MarkdownStore(tmp_path, segment="proj")
        with pytest.raises(FormError):
            store.path_for("../escape")


class TestSegmentEdgeCases:
    """Empty string segment behaves like no segment."""

    def test_empty_string_segment_behaves_flat(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path, segment="")
        assert store._directory == tmp_path

        store.create("flat-entity", attributes={})
        assert (tmp_path / "flat-entity.md").is_file()

    def test_none_segment_behaves_flat(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path, segment=None)
        assert store._directory == tmp_path

        store.create("flat-entity", attributes={})
        assert (tmp_path / "flat-entity.md").is_file()
