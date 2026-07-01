"""Tests for MarkdownStore.get."""

from pathlib import Path

import pytest


class TestGet:
    """Tests for MarkdownStore.get."""

    def test_get_returns_entity_from_file(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create(
            "entity-1",
            attributes={"title": "Test", "score": 42},
            body="some content",
        )

        entity = store.get("entity-1")

        assert entity.id == "entity-1"
        assert entity.body == "some content"
        assert entity.attributes["title"] == "Test"
        assert entity.attributes["score"] == 42

    def test_get_missing_id_raises_not_found_error(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore, NotFoundError

        store = MarkdownStore(tmp_path)

        with pytest.raises(NotFoundError):
            store.get("ghost")

    def test_get_applies_normalize_hook_to_frontmatter(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        store.create("entity-1", attributes={"title": "Test"})

        def normalize(fm):
            fm["extra"] = "x"
            return fm

        entity = store.get("entity-1", normalize=normalize)

        assert entity.attributes["extra"] == "x"

    def test_get_without_normalize_keeps_frontmatter_unchanged(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        store.create("entity-2", attributes={"title": "Test"})

        entity = store.get("entity-2")

        assert "extra" not in entity.attributes
