from datetime import UTC

import pytest
from pydantic import ValidationError
from ruamel.yaml import CommentedMap

from micro_entity.codec import CodecError, entity_from_parts, parse_document, serialize_document
from micro_entity.entity import Entity


class TestParseDocument:
    """Tests for parse_document function."""

    def test_frontmatter_and_body(self):
        """Both frontmatter dict and body text returned."""
        text = "---\nname: test\nage: 30\n---\nThis is the body."
        fm, body = parse_document(text)

        assert isinstance(fm, CommentedMap)
        assert fm["name"] == "test"
        assert fm["age"] == 30
        assert body == "This is the body."

    def test_frontmatter_only_no_body(self):
        """Body is None when nothing after closing ---."""
        text = "---\nname: test\n---\n"
        fm, body = parse_document(text)

        assert isinstance(fm, CommentedMap)
        assert fm["name"] == "test"
        assert body is None

    def test_frontmatter_only_no_trailing_newline(self):
        """Body is None when file ends immediately after closing ---."""
        text = "---\nname: test\n---"
        fm, body = parse_document(text)

        assert fm["name"] == "test"
        assert body is None

    def test_empty_body_whitespace_returns_none(self):
        """Whitespace-only body returns None."""
        text = "---\ntitle: doc\n---\n  \n\n  \n"
        fm, body = parse_document(text)

        assert fm["title"] == "doc"
        assert body is None

    def test_preserves_key_order(self):
        """YAML CommentedMap preserves insertion order."""
        text = "---\nfirst: 1\nsecond: 2\nthird: 3\n---\nbody"
        fm, _ = parse_document(text)

        keys = list(fm.keys())
        assert keys == ["first", "second", "third"]

    def test_preserves_comments(self):
        """Comments in frontmatter retained and re-emittable via YAML dump."""
        from io import StringIO

        from ruamel.yaml import YAML

        text = "---\n# This is a comment\nname: test\n---\nBody here."
        fm, body = parse_document(text)

        assert fm.ca is not None  # CommentedMap stores comments in ca attribute
        assert body == "Body here."

        # Verify by re-emitting through YAML round-trip
        stream = StringIO()
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.dump(fm, stream)
        dumped = stream.getvalue()
        assert "#" in dumped

    def test_no_opening_delimiter_raises(self):
        """Missing opening --- raises CodecError."""
        with pytest.raises(CodecError, match=r"opening"):
            parse_document("name: test\n---\nbody")

    def test_no_closing_delimiter_raises(self):
        """Unterminated frontmatter (no closing ---) raises CodecError."""
        with pytest.raises(CodecError, match=r"closing"):
            parse_document("---\nname: test\nbody text without delimiter")

    def test_non_mapping_frontmatter_raises(self):
        """YAML frontmatter that parses as a list/scalar raises CodecError."""
        with pytest.raises(CodecError):
            parse_document("---\n- item1\n- item2\n---\nbody")

    def test_scalar_frontmatter_raises(self):
        """Scalar YAML values as frontmatter raise CodecError."""
        with pytest.raises(CodecError):
            parse_document("---\njust a string\n---\nbody")

    def test_empty_document_raises(self):
        """Completely empty document raises CodecError."""
        with pytest.raises(CodecError, match=r"opening"):
            parse_document("")

    def test_whitespace_only_document_raises(self):
        """Whitespace-only document raises CodecError."""
        with pytest.raises(CodecError, match=r"opening"):
            parse_document("   \n\n  ")

    def test_multiline_body(self):
        """Body with multiple lines preserved exactly."""
        text = "---\ntitle: Hello\n---\nLine one\nLine two\nLine three\n"
        _, body = parse_document(text)
        assert body == "Line one\nLine two\nLine three\n"

    def test_empty_frontmatter_block(self):
        """Empty YAML block between --- delimiters produces empty CommentedMap."""
        text = "---\n---\nbody"
        fm, body = parse_document(text)

        assert isinstance(fm, CommentedMap)
        assert len(fm) == 0
        assert body == "body"


class TestSerializeDocument:
    """Tests for serialize_document function."""

    def test_roundtrip_preserves_text(self):
        """parse -> serialize produces byte-identical original."""
        text = "---\nname: test\nage: 30\n---\nThis is the body."
        fm, body = parse_document(text)
        result = serialize_document(fm, body)
        assert result == text

    def test_body_none_no_trailing_newline(self):
        """body=None → ends with ---, no trailing newline."""
        fm, _ = parse_document("---\nname: test\n---")
        result = serialize_document(fm, None)
        assert result == "---\nname: test\n---"

    def test_body_empty_string_trailing_newline(self):
        """body='' → ends with ---\\n (empty body region exists)."""
        fm, _ = parse_document("---\nname: test\n---\n")
        result = serialize_document(fm, "")
        assert result == "---\nname: test\n---\n"

    def test_body_nonempty_preserved_verbatim(self):
        """body text passes through unchanged."""
        body_text = "hello\nworld\n"
        fm = CommentedMap({"title": "doc"})
        result = serialize_document(fm, body_text)
        assert result.endswith(body_text)

    def test_comments_preserved_on_roundtrip(self):
        """Comments in frontmatter survive parse+serialize."""
        text = "---\n# This is a comment\nname: test\n---\nBody here."
        fm, body = parse_document(text)
        result = serialize_document(fm, body)
        # Both original and round-trip should contain the comment
        assert "#" in result

    def test_key_order_preserved(self):
        """Key ordering in frontmatter is preserved."""
        text = "---\nfirst: 1\nsecond: 2\nthird: 3\n---\nbody"
        fm, body = parse_document(text)
        result = serialize_document(fm, body)
        keys_in_order = list(fm.keys())
        # After re-parse, order must match original
        fm2, _ = parse_document(result)
        assert list(fm2.keys()) == keys_in_order

    def test_multiline_body_preserved(self):
        """Multi-line body survives roundtrip."""
        text = "---\ntitle: Hello\n---\nLine one\nLine two\nLine three\n"
        fm, body = parse_document(text)
        result = serialize_document(fm, body)
        assert result == text

    def test_roundtrip_stability_three_cycles(self):
        """parse->serialize repeated 3× yields immutable result."""
        text = "---\nname: test\n---\nBody line 1\nBody line 2\n"
        result = text
        for _ in range(3):
            fm, body = parse_document(result)
            result = serialize_document(fm, body)
        assert result == text

    def test_codec_error_is_value_error(self):
        """CodecError subclasses ValueError."""
        assert issubclass(CodecError, ValueError)
        try:
            raise CodecError("test error")
        except ValueError:
            pass  # should catch
        else:
            pytest.fail("CodecError did not raise as ValueError")


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
