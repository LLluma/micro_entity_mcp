from datetime import UTC

from ruamel.yaml import CommentedMap

from micro_entity.codec import (
    entity_from_parts,
    entity_to_parts,
    parse_document,
    serialize_document,
)
from micro_entity.entity import Entity


class TestEntityToParts:
    """Tests for entity_to_parts function."""

    def _ts(self):
        """Return default entity timestamps (UTC)."""
        from datetime import datetime as _dt

        return (
            _dt(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            _dt(2024, 2, 20, 12, 0, 0, tzinfo=UTC),
        )

    def _make_entity(self, **overrides):
        """Helper: create a default Entity, override fields."""
        from datetime import datetime as _dt

        defaults = {
            "id": "myfile",
            "created": _dt(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            "updated": _dt(2024, 2, 20, 12, 0, 0, tzinfo=UTC),
            "body": None,
            "attributes": {},
        }
        defaults.update(overrides)
        return Entity(**defaults)

    def test_basic_entity_to_parts(self):
        """Entity with timestamps and attributes → CommentedMap + body."""
        entity = self._make_entity(
            body="hello world",
            attributes={"tags": ["a", "b"], "priority": 1},
        )

        fm, body = entity_to_parts(entity)

        assert isinstance(fm, CommentedMap)
        assert body == "hello world"
        assert "created" in fm
        assert "updated" in fm
        assert isinstance(fm["created"], str)
        assert isinstance(fm["updated"], str)

    def test_id_not_in_frontmatter(self):
        """id does NOT appear in emitted frontmatter."""
        entity = self._make_entity()

        fm, _ = entity_to_parts(entity)

        assert list(fm.keys()) == ["created", "updated"]

    def test_body_none_returns_none(self):
        """body=None → (frontmatter, None)."""
        entity = self._make_entity(body=None)

        _, body = entity_to_parts(entity)
        assert body is None

    def test_body_empty_string(self):
        """body='' → (frontmatter, '')."""
        entity = self._make_entity(body="")

        _, body = entity_to_parts(entity)
        assert body == ""

    def test_body_text_passed_through(self):
        """body text passes through unchanged."""
        entity = self._make_entity(body="some text")

        _, body = entity_to_parts(entity)
        assert body == "some text"

    def test_timestamps_are_iso_strings(self):
        """Timestamps emit as ISO-8601 strings, not datetime objects."""
        from datetime import datetime as _dt

        entity = Entity(
            id="myfile",
            created=_dt(2024, 1, 15, 10, 30, 45, tzinfo=UTC),
            updated=_dt(2024, 2, 20, 23, 59, 59, 123456, tzinfo=UTC),
            body=None,
            attributes={},
        )

        fm, _ = entity_to_parts(entity)

        assert isinstance(fm["created"], str)
        assert isinstance(fm["updated"], str)
        parsed = _dt.fromisoformat(fm["created"])
        assert parsed == entity.created
        parsed2 = _dt.fromisoformat(fm["updated"])
        assert parsed2 == entity.updated

    def test_all_attributes_emitted(self):
        """All entity attributes appear in frontmatter."""
        entity = self._make_entity(
            attributes={"name": "test", "count": 42, "active": True},
        )

        fm, _ = entity_to_parts(entity)

        assert fm["name"] == "test"
        assert fm["count"] == 42
        assert fm["active"] is True

    def test_frontmatter_contains_no_body_key(self):
        """body is NOT emitted as a frontmatter key."""
        entity = self._make_entity(body="some text")

        fm, _ = entity_to_parts(entity)

        assert "body" not in fm

    def test_roundtrip_entity_parts_doc_parts_entity(self):
        """Full round-trip: entity → parts → doc → parse → entity_from_parts.

        entity_to_parts → serialize_document → parse_document → entity_from_parts
        yields an entity equal to the original.
        """
        entity = Entity(
            id="myfile",
            created=self._ts()[0],
            updated=self._ts()[1],
            body="hello there",
            attributes={"tags": ["a", "b"], "priority": 3, "title": "doc"},
        )

        fm, body = entity_to_parts(entity)
        doc = serialize_document(fm, body)
        fm2, body2 = parse_document(doc)
        reconstructed = entity_from_parts("myfile", fm2, body2)

        assert reconstructed.created == entity.created
        assert reconstructed.updated == entity.updated
        assert reconstructed.body == entity.body
        assert reconstructed.attributes == entity.attributes

    def test_roundtrip_no_body(self):
        """Round-trip with body=None."""
        entity = self._make_entity(
            body=None,
            attributes={"key": "val"},
        )

        fm, body = entity_to_parts(entity)
        doc = serialize_document(fm, body)
        fm2, body2 = parse_document(doc)
        reconstructed = entity_from_parts("myfile", fm2, body2)

        assert doc.endswith("\n")
        assert not doc.endswith("\n\n")
        assert reconstructed.body is None
        assert reconstructed.attributes == entity.attributes

    def test_deterministic_order(self):
        """Frontmatter key order is deterministic (insertion order)."""
        entity = self._make_entity(
            attributes={"z_last": 1, "a_first": 2, "m_mid": 3},
        )

        fm, _ = entity_to_parts(entity)
        keys = list(fm.keys())

        assert keys[:2] == ["created", "updated"]
        assert keys[2:] == ["z_last", "a_first", "m_mid"]

    def test_empty_attributes(self):
        """Entity with no attributes → only created/updated in frontmatter."""
        entity = self._make_entity(attributes={})

        fm, _ = entity_to_parts(entity)

        assert list(fm.keys()) == ["created", "updated"]
        assert len(fm) == 2
