"""Tests for MarkdownStore."""

from datetime import UTC, datetime
from pathlib import Path

import pytest


class TestCreate:
    """Tests for MarkdownStore.create."""

    def test_create_writes_parseable_markdown_file(self, tmp_path: Path) -> None:
        from micro_entity.codec import parse_document
        from micro_entity.markdown_store import MarkdownStore

        called: list[datetime] = []

        def fake_clock() -> datetime:
            dt = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
            called.append(dt)
            return dt

        store = MarkdownStore(tmp_path, clock=fake_clock)
        entity = store.create("entity-1", attributes={"role": "admin"}, body="hello")

        # Returned entity has created == updated == clock value
        assert entity.id == "entity-1"
        assert entity.created == called[0]
        assert entity.updated == called[0]
        assert entity.body == "hello"
        assert entity.attributes == {"role": "admin"}

        # File exists
        path = tmp_path / "entity-1.md"
        assert path.is_file()

        # File is parseable by codec
        fm, body = parse_document(path.read_text(encoding="utf-8"))
        assert str(fm["created"]) == "2025-01-15T10:00:00+00:00"
        assert str(fm["updated"]) == "2025-01-15T10:00:00+00:00"
        assert fm["role"] == "admin"
        assert body == "hello"

    def test_create_returns_entity_with_equal_timestamps(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        def fake_clock() -> datetime:
            return datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)

        store = MarkdownStore(tmp_path, clock=fake_clock)

        entity = store.create("noattr", attributes={})

        # Both timestamps come from the same clock invocation => equality
        assert entity.created == entity.updated


class TestCreateFileExists:
    """Tests for MarkdownStore.create duplicate handling."""

    def test_create_existing_id_raises_file_exists_error(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("dup", attributes={})
        with pytest.raises(FileExistsError):
            store.create("dup", attributes={})


class TestCreateValidation:
    """Tests for MarkdownStore.create bad attribute validation."""

    def test_bad_attribute_value_raises_before_file_written(self, tmp_path: Path) -> None:

        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.validation import FormError

        store = MarkdownStore(tmp_path)

        # Nested list is rejected by attribute validation (checked at the store layer,
        # so no partial file is left on disk before any I/O).
        with pytest.raises(FormError):
            store.create(
                "badval",
                attributes={"tags": [[1, 2]]},  # type: ignore[arg-type]
            )

    def test_invalid_id_raises(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.validation import FormError

        store = MarkdownStore(tmp_path)

        with pytest.raises(FormError):
            store.create("../bad", attributes={})


class TestCreateRoundTrip:
    """Tests for MarkdownStore.create round-trip."""

    def test_attributes_round_trip(self, tmp_path: Path) -> None:
        from micro_entity.codec import parse_document
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create(
            "rt",
            attributes={
                "name": "test",
                "score": 42,
                "enabled": True,
                "ratio": 3.14,
                "tags": ["a", "b", "c"],
            },
        )

        path = tmp_path / "rt.md"
        fm, body = parse_document(path.read_text(encoding="utf-8"))

        assert fm["name"] == "test"
        assert fm["score"] == 42
        assert fm["enabled"] is True
        assert abs(float(fm["ratio"]) - 3.14) < 0.01
        # list is preserved by ruamel.yaml
        assert list(fm["tags"]) == ["a", "b", "c"]
        assert body is None


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
