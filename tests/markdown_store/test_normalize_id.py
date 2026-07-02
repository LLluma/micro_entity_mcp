"""Tests for MarkdownStore id-normalization hook."""

from pathlib import Path

import pytest

from micro_entity.markdown_store import MarkdownStore


def _digit_pad(s: str) -> str:
    """Zero-pad digits: ``'17'`` → ``'0017'``."""
    return f"{int(s):04d}" if s.isdigit() else s


class TestDefaultNormalizer:
    """No normalizer injected — identity must be unchanged."""

    def test_normalize_id_is_identity(self, tmp_path: Path) -> None:
        store = MarkdownStore(tmp_path)
        assert store.normalize_id("abc") == "abc"
        assert store.normalize_id("my-id") == "my-id"

    def test_path_for_unchanged_without_normalizer(self, tmp_path: Path) -> None:
        store = MarkdownStore(tmp_path)
        result = store.path_for("abc")
        assert result.name == "abc.md"


@pytest.fixture()
def padded_store(tmp_path: Path) -> MarkdownStore:
    # zero-pad digits: "17" → "0017"
    return MarkdownStore(tmp_path, normalize_id=_digit_pad)


class TestInjectedNormalizer:
    """A digit-zero-pad normalizer demonstrates correct lookup behaviour."""

    def test_normalize_id_pads_digits(self, padded_store: MarkdownStore) -> None:
        store = padded_store
        assert store.normalize_id("17") == "0017"
        assert store.normalize_id("0") == "0000"
        # non-digit id is unchanged
        assert store.normalize_id("alpha") == "alpha"

    def test_path_for_resolves_normalized_file(self, padded_store: MarkdownStore) -> None:
        """path_for("17") → .../0017.md"""
        result = padded_store.path_for("17")
        assert result.name == "0017.md"

    def test_create_then_get_via_unpadded_id(self, padded_store: MarkdownStore) -> None:
        """Create stores at padded name; unpadded lookup returns same entity."""
        store = padded_store
        store.create("17", attributes={"title": "padded"})
        entity = store.get("17")
        assert entity.id == "17"
        assert entity.attributes["title"] == "padded"

    def test_exists_returns_true_after_normalized_create(self, padded_store: MarkdownStore) -> None:
        store = padded_store
        store.create("17", attributes={})
        assert store.exists("17") is True
