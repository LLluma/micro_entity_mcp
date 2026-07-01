import pytest
from ruamel.yaml import CommentedMap

from micro_entity.codec import CodecError, parse_document


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
