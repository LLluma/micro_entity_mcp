from datetime import UTC

import pytest
from pydantic import ValidationError
from ruamel.yaml import CommentedMap

from micro_entity.codec import CodecError, entity_from_parts
from micro_entity.entity import Entity


class TestEntityFromParts:
    """Tests for entity_from_parts function."""

    def test_wellformed_frontmatter_builds_entity(self):
        """Valid frontmatter yields Entity with correct fields."""
        from datetime import datetime

        fm = CommentedMap(
            {
                "created": datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                "updated": datetime(2024, 2, 20, 12, 0, 0, tzinfo=UTC),
                "tags": ["a", "b"],
                "priority": 1,
            }
        )
        entity = entity_from_parts("myfile", fm, "hello body")

        assert entity.id == "myfile"
        assert entity.created == fm["created"]
        assert entity.updated == fm["updated"]
        assert entity.body == "hello body"
        assert entity.attributes == {"tags": ["a", "b"], "priority": 1}

    def test_iso_string_timestamps_parse(self):
        """ISO-8601 string timestamps are parsed to datetime."""
        from datetime import datetime as _dt

        fm = CommentedMap(
            {
                "created": "2024-01-15T10:30:00+00:00",
                "updated": "2024-02-20T12:00:00+00:00",
            }
        )
        entity = entity_from_parts("myfile", fm, None)

        assert isinstance(entity.created, _dt)
        assert isinstance(entity.updated, _dt)
        assert entity.created.year == 2024
        assert entity.created.month == 1
        assert entity.body is None
        assert entity.attributes == {}

    def test_missing_created_raises_codec_error(self):
        """Missing 'created' key raises CodecError naming the field."""
        fm = CommentedMap({"updated": "2024-01-01T00:00:00+00:00"})
        with pytest.raises(CodecError, match=r"created"):
            entity_from_parts("myfile", fm, None)

    def test_missing_updated_raises_codec_error(self):
        """Missing 'updated' key raises CodecError naming the field."""
        fm = CommentedMap({"created": "2024-01-01T00:00:00+00:00"})
        with pytest.raises(CodecError, match=r"updated"):
            entity_from_parts("myfile", fm, None)

    def test_unparseable_timestamp_raises_codec_error(self):
        """Unparseable timestamp string raises CodecError."""
        fm = CommentedMap(
            {
                "created": "not-a-date",
                "updated": "2024-01-01T00:00:00+00:00",
            }
        )
        with pytest.raises(CodecError, match=r"created"):
            entity_from_parts("myfile", fm, None)

    def test_bad_id_propagates_entity_validation_error(self):
        """Invalid id propagates Entity validation error unchanged."""
        from datetime import datetime

        fm = CommentedMap(
            {
                "created": datetime.now(tz=UTC),
                "updated": datetime.now(tz=UTC),
            }
        )
        with pytest.raises(ValidationError):
            entity_from_parts("bad id!", fm, None)

    def test_empty_attribute_key_propagates_entity_validation_error(self):
        """Empty key in attributes triggers Entity validation error."""
        from datetime import datetime

        fm = CommentedMap(
            {
                "created": datetime.now(tz=UTC),
                "updated": datetime.now(tz=UTC),
                "": "bad-key",
            }
        )
        with pytest.raises(ValidationError):
            entity_from_parts("myfile", fm, None)

    def test_nested_attribute_value_propagates_entity_validation_error(self):
        """Nested dict value triggers Entity validation error."""
        from datetime import datetime

        fm = CommentedMap(
            {
                "created": datetime.now(tz=UTC),
                "updated": datetime.now(tz=UTC),
                "nested": {"key": "val"},
            }
        )
        with pytest.raises(ValidationError):
            entity_from_parts("myfile", fm, None)

    def test_no_body_passes(self):
        """body=None is accepted."""
        from datetime import datetime

        fm = CommentedMap(
            {
                "created": datetime.now(tz=UTC),
                "updated": datetime.now(tz=UTC),
            }
        )
        entity = entity_from_parts("myfile", fm, None)

        assert entity.body is None

    def test_entity_is_type_entity(self):
        """Return value is an Entity instance."""
        from datetime import datetime

        fm = CommentedMap(
            {
                "created": datetime.now(tz=UTC),
                "updated": datetime.now(tz=UTC),
            }
        )
        entity = entity_from_parts("myfile", fm, None)

        assert isinstance(entity, Entity)
