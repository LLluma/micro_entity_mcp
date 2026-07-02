"""Test :func:`_normalize_adr_id` — canonicalize ADR id strings."""

import pytest

from servers.adr import _normalize_adr_id


def test_bare_single_digit():
    assert _normalize_adr_id("7") == "ADR-0007"


def test_bare_two_digits():
    assert _normalize_adr_id("14") == "ADR-0014"


def test_prefixed_with_hyphen():
    assert _normalize_adr_id("ADR-7") == "ADR-0007"


def test_prefixed_lowercase():
    assert _normalize_adr_id("adr-0007") == "ADR-0007"


def test_prefixed_no_hyphen():
    assert _normalize_adr_id("adr7") == "ADR-0007"


def test_idempotent_canonical():
    assert _normalize_adr_id("ADR-0014") == "ADR-0014"


def test_wide_number_keeps_width():
    assert _normalize_adr_id("ADR-12345") == "ADR-12345"


def test_empty_string():
    assert _normalize_adr_id("") == ""


def test_unknown_token_unchanged():
    assert _normalize_adr_id("foo") == "foo"


def test_trailing_hyphen_dash_unchanged():
    assert _normalize_adr_id("ADR-0007-x") == "ADR-0007-x"


def test_trailing_dash_no_digits():
    assert _normalize_adr_id("ADR-") == "ADR-"


@pytest.mark.parametrize(
    "normalizer",
    [
        lambda v: _normalize_adr_id(_normalize_adr_id(v)) == _normalize_adr_id(v),
    ],
    ids=["apply-twice-equals-once"],
)
def test_idempotence_matching(normalizer):
    """Idempotence for inputs the regex matches."""
    assert normalizer("7")
    assert normalizer("ADR-7")
    assert normalizer("adr7")
    assert normalizer("ADR-0014")
    assert normalizer("ADR-12345")


@pytest.mark.parametrize(
    "normalizer",
    [
        lambda v: _normalize_adr_id(_normalize_adr_id(v)) == _normalize_adr_id(v),
    ],
    ids=["apply-twice-equals-once"],
)
def test_idempotence_non_matching(normalizer):
    """Idempotence for inputs that pass through unchanged."""
    assert normalizer("")
    assert normalizer("foo")
    assert normalizer("ADR-0007-x")
    assert normalizer("ADR-")
