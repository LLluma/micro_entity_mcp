"""Tests for _normalize_todo_id — pure string normalization."""

from servers.todo import _normalize_todo_id


class TestNormalizeTodoIdDigitPadded:
    """Digit-only strings get zero-padded to at least width 4."""

    def test_short_17(self):
        assert _normalize_todo_id("17") == "0017"

    def test_short_42(self):
        assert _normalize_todo_id("42") == "0042"

    def test_short_1(self):
        assert _normalize_todo_id("1") == "0001"


class TestNormalizeTodoIdIdempotentCanonical:
    """Already-canonical ids stay unchanged (idempotent on canonical form)."""

    def test_canonical_0017(self):
        assert _normalize_todo_id("0017") == "0017"


class TestNormalizeTodoIdWideNumbers:
    """Numbers wider than 4 digits keep their width — not truncated."""

    def test_five_digits(self):
        assert _normalize_todo_id("12345") == "12345"


class TestNormalizeTodoIdNonDigit:
    """Non-digit strings pass through unchanged."""

    def test_alpha(self):
        assert _normalize_todo_id("abc") == "abc"

    def test_mixed(self):
        assert _normalize_todo_id("12a") == "12a"

    def test_empty(self):
        assert _normalize_todo_id("") == ""


class TestNormalizeTodoIdIdempotence:
    """Applying twice yields the same result as applying once."""

    def test_digit_idempotent(self):
        val = _normalize_todo_id("17")
        assert _normalize_todo_id(val) == val

    def test_non_digit_idempotent(self):
        val = _normalize_todo_id("abc")
        assert _normalize_todo_id(val) == val
