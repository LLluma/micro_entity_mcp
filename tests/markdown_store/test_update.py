"""Tests for MarkdownStore.update."""

from datetime import UTC, datetime
from pathlib import Path

import pytest


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


class TestUpdateNormalize:
    """Tests for MarkdownStore.update normalize hook."""

    def test_update_applies_normalize_before_patching(self, tmp_path: Path) -> None:
        from micro_entity.codec import parse_document
        from micro_entity.markdown_store import MarkdownStore

        store = MarkdownStore(tmp_path)
        store.create("norm", attributes={"title": "Test"}, body="body")

        def normalize(fm):
            fm["migrated"] = "yes"
            return fm

        store.update("norm", attributes={"title": "Updated"}, normalize=normalize)

        fm, body = parse_document((tmp_path / "norm.md").read_text(encoding="utf-8"))
        assert fm["migrated"] == "yes"
        assert fm["title"] == "Updated"
        assert body == "body"


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
