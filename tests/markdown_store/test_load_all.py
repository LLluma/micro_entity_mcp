"""Tests for MarkdownStore.load_all."""

from pathlib import Path

import pytest


class TestLoadAllNormalize:
    """Tests for MarkdownStore.load_all normalize hook."""

    def test_load_all_applies_normalize_to_each_record(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        store.create("one", attributes={"title": "One"})
        store.create("two", attributes={"title": "Two"})

        def normalize(fm):
            fm["loaded"] = True
            return fm

        entities, errors = store.load_all(normalize=normalize)

        assert errors == []
        assert [entity.attributes["loaded"] for entity in entities] == [True, True]


class TestLoadAll:
    """Tests for MarkdownStore.load_all."""

    def test_load_all_returns_all_entities_sorted_by_id(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("charlie", attributes={"x": 3})
        store.create("alpha", attributes={"x": 1})
        store.create("bravo", attributes={"x": 2})

        entities, errors = store.load_all()

        assert errors == []
        assert len(entities) == 3
        ids = [e.id for e in entities]
        assert ids == ["alpha", "bravo", "charlie"]

    def test_load_all_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        entities, errors = store.load_all()

        assert entities == []
        assert errors == []

    def test_load_all_malformed_file_quarantines_error(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("good", attributes={"ok": True})
        path_bad = tmp_path / "bad.md"
        path_bad.write_text("not a valid document at all\n", encoding="utf-8")

        entities, errors = store.load_all()

        assert len(entities) == 1
        assert entities[0].id == "good"
        assert len(errors) == 1
        assert errors[0].id == "bad"
        assert "not a valid document" in errors[0].reason or "Missing" in errors[0].reason

    def test_load_all_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        import shutil

        from micro_entity.markdown_store import MarkdownStore

        gone = tmp_path / "gone"
        gone.mkdir()
        store = MarkdownStore(gone)
        # Force the directory away so is_dir() returns False
        shutil.rmtree(gone)

        entities, errors = store.load_all()

        assert entities == []
        assert errors == []

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
