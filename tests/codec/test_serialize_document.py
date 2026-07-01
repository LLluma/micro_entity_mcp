import pytest
from ruamel.yaml import CommentedMap

from micro_entity.codec import CodecError, parse_document, serialize_document


class TestSerializeDocument:
    """Tests for serialize_document function."""

    def test_roundtrip_preserves_text(self):
        """parse -> serialize produces byte-identical original."""
        text = "---\nname: test\nage: 30\n---\nThis is the body."
        fm, body = parse_document(text)
        result = serialize_document(fm, body)
        assert result == text

    def test_body_none_trailing_newline_once(self):
        """body=None → ends with exactly one trailing newline."""
        fm, _ = parse_document("---\nname: test\n---")
        result = serialize_document(fm, None)
        assert result == "---\nname: test\n---\n"
        assert result.endswith("\n")
        assert not result.endswith("\n\n")

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
