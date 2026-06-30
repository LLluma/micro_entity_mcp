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


class TestUpdateTimestamps:
    """Tests for MarkdownStore.update timestamp behaviour."""

    def test_updated_advances_created_stays(self, tmp_path: Path) -> None:
        from datetime import timedelta

        from micro_entity.markdown_store import MarkdownStore

        base = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        seq = [0]

        def ticking_clock():
            seq[0] += 1
            return base + timedelta(seconds=seq[0] * 3600)

        store = MarkdownStore(tmp_path, clock=ticking_clock)

        entity = store.create("ts-test", attributes={"role": "admin"})
        created_ts = entity.created
        assert entity.updated == created_ts

        entity2 = store.update("ts-test", attributes={"role": "user"})
        assert entity2.created == created_ts
        assert entity2.updated > created_ts


class TestUpdateBody:
    """Tests for MarkdownStore.update body handling."""

    def test_body_left_untouched_when_unset(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("bbody", attributes={"x": 1}, body="original body")

        entity2 = store.update("bbody", attributes={"y": 2})
        assert entity2.body == "original body"

        # Verify on disk — file should still contain old body
        raw = (tmp_path / "bbody.md").read_text(encoding="utf-8")
        assert "original body" in raw

    def test_body_replaced_when_explicit(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("bbody2", attributes={"x": 1}, body="original")

        entity2 = store.update("bbody2", body="replaced body", attributes={"z": 3})
        assert entity2.body == "replaced body"

    def test_body_none_removes_body_region(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create("bbody3", attributes={"x": 1}, body="to remove")

        entity2 = store.update("bbody3", body=None)
        assert entity2.body is None

        raw = (tmp_path / "bbody3.md").read_text(encoding="utf-8")
        # No body region should appear after closing ---
        parts = raw.split("---", 2)
        assert "\n" not in parts[2].strip() or parts[2].strip() == ""


class TestUpdateCommentPreservation:
    """Tests for MarkdownStore.update preserving YAML comments and key order."""

    def test_update_preserves_yaml_comments_and_key_order(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)

        store.create(
            "commented",
            attributes={"role": "admin", "score": 42},
            body="hello world",
        )

        # Manually rewrite the file inserting YAML comments, like a human editor would.
        path = tmp_path / "commented.md"
        patched = (
            "---\n"
            "created: '2025-01-15T10:00:00+00:00'\n"
            "updated: '2025-01-15T10:00:00+00:00'\n"
            "role: admin  # the user role\n"
            "score: 42  # integer score\n"
            "---\n"
            "hello world\n"
        )
        path.write_text(patched, encoding="utf-8")

        # Now update one attribute — the others and comments must survive.
        store.update("commented", attributes={"score": 99})

        raw = path.read_text(encoding="utf-8")

        # The old role comment must still be present.
        assert "# the user role" in raw
        # The score comment must still be present (key was patched in-place).
        assert "# integer score" in raw
        # The key order: role before score must be preserved.
        role_pos = raw.index("role:")
        score_pos = raw.index("score:")
        assert role_pos < score_pos
        # The updated value must reflect the change.
        assert "score: 99" in raw
        # Body preserved.
        assert "hello world" in raw


class TestUpdateInvalidAttribute:
    """Tests for MarkdownStore.update validation before write."""

    def test_bad_attribute_value_raises_and_does_not_modify_disk(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore
        from micro_entity.validation import FormError

        store = MarkdownStore(tmp_path)

        store.create("safe", attributes={"role": "admin", "score": 42}, body="original")

        before_path = tmp_path / "safe.md"
        before_text = before_path.read_text(encoding="utf-8")

        with pytest.raises(FormError):
            store.update(
                "safe",
                attributes={"role": [[1, 2]]},  # type: ignore[arg-type]
            )

        after_text = before_path.read_text(encoding="utf-8")
        assert after_text == before_text


class TestUpdateMissingId:
    """Tests for MarkdownStore.update on a non-existent entity."""

    def test_update_missing_id_raises_not_found_error(self, tmp_path: Path) -> None:
        from micro_entity.markdown_store import MarkdownStore, NotFoundError

        store = MarkdownStore(tmp_path)

        with pytest.raises(NotFoundError):
            store.update("ghost", attributes={"x": 1})


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
