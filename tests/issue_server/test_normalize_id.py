"""Tests for ``_normalize_issue_id``."""

import pytest

from servers.issue import _normalize_issue_id


class TestBareDigits:
    """All-digit strings are normalised to ISSUE-NNNN."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("7", "ISSUE-0007"),
            ("42", "ISSUE-0042"),
            ("12345", "ISSUE-12345"),
        ],
    )
    def test_bare_digits(self, raw, expected):
        assert _normalize_issue_id(raw) == expected


class TestCanonicalAlready:
    """A canonical id stays unchanged (idempotence anchor)."""

    @pytest.mark.parametrize(
        "raw",
        [
            "ISSUE-0007",
            "ISSUE-0042",
            "ISSUE-12345",
        ],
    )
    def test_preserves_canonical(self, raw):
        assert _normalize_issue_id(raw) == raw


class TestCaseInsensitivePrefix:
    """Any casing of ISSUE (with or without hyphen) normalises."""

    @pytest.mark.parametrize(
        "raw",
        [
            "issue-7",
            "Issue7",
            "ISSUE7",
            "iSsUe-007",
        ],
    )
    def test_case_variants(self, raw):
        assert _normalize_issue_id(raw) == "ISSUE-0007"


class TestUnchanged:
    """Non-matching strings pass through verbatim."""

    @pytest.mark.parametrize(
        "raw",
        [
            "abc",
            "ISSUE-",
            "FOO-1",
            "",
        ],
    )
    def test_passthrough(self, raw):
        assert _normalize_issue_id(raw) == raw


class TestIdempotence:
    """normalize(normalize(x)) == normalize(x) for a representative set."""

    @pytest.mark.parametrize(
        "input_val",
        [
            # digits
            "7",
            "42",
            "12345",
            # mixed-case prefixes
            "issue-7",
            "Issue7",
            "ISSUE7",
            "iSsUe-007",
            # already normal
            "ISSUE-0007",
            "ISSUE-12345",
            # non-matching
            "abc",
            "ISSUE-",
            "FOO-1",
            "",
        ],
    )
    def test_idempotent(self, input_val):
        first = _normalize_issue_id(input_val)
        second = _normalize_issue_id(first)
        assert first == second
