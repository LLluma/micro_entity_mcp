"""Tests for match_attribute in micro_entity/query.py."""

from datetime import UTC, datetime

from micro_entity.entity import Entity
from micro_entity.query import match_attribute
from micro_entity.validation import Scalar

_fixture_ts = datetime(2024, 1, 1, tzinfo=UTC)


def _entity(attrs: dict[str, Scalar | list[Scalar]]) -> Entity:
    return Entity(id="e1", created=_fixture_ts, updated=_fixture_ts, attributes=attrs)


# --- scalar attribute equal / unequal ---


class TestScalarEqual:
    def test_scalar_match(self) -> None:
        """scalar attr value equals query value -> True"""
        e = _entity({"color": "red"})
        assert match_attribute(e, "color", ["red"]) is True

    def test_scalar_unequal(self) -> None:
        """scalar attr value no match -> False"""
        e = _entity({"color": "red"})
        assert match_attribute(e, "color", ["blue"]) is False

    def test_scalar_missing_key(self) -> None:
        """key not in attributes -> False"""
        e = _entity({"color": "red"})
        assert match_attribute(e, "missing", ["red"]) is False


# --- list attribute ---


class TestListAttr:
    def test_list_shares_value(self) -> None:
        """list attr & query values share >=1 element -> True"""
        e = _entity({"tags": ["a", "b", "c"]})
        assert match_attribute(e, "tags", ["x", "b"]) is True

    def test_list_disjoint(self) -> None:
        """no overlap between list attr & query values -> False"""
        e = _entity({"tags": ["a", "b"]})
        assert match_attribute(e, "tags", ["x", "y"]) is False


# --- empty values ---


class TestEmptyValues:
    def test_empty_values_returns_false(self) -> None:
        assert match_attribute(_entity({"x": 1}), "x", []) is False


# --- type-strict ---


class TestTypeStrict:
    def test_int_vs_str(self) -> None:
        """int 1 vs str '1' -> False"""
        e = _entity({"count": 1})
        assert match_attribute(e, "count", ["1"]) is False

    def test_int_vs_float(self) -> None:
        """int 1 vs float 1.0 -> False"""
        e = _entity({"count": 1})
        assert match_attribute(e, "count", [1.0]) is False

    def test_bool_vs_int(self) -> None:
        """bool True vs int 1 -> False"""
        e = _entity({"flag": True})
        assert match_attribute(e, "flag", [1]) is False

    def test_scalar_int_match(self) -> None:
        """matching int vs int -> True"""
        e = _entity({"count": 1})
        assert match_attribute(e, "count", [1]) is True

    def test_list_mixed_type_strict(self) -> None:
        """list attr with mixed types, one int match should succeed"""
        e = _entity({"items": ["x", 42, "y"]})
        assert match_attribute(e, "items", [0, 42]) is True


# --- case-sensitive ---


class TestCaseSensitive:
    def test_case_mismatch(self) -> None:
        """'Tag' vs 'tag' -> False"""
        e = _entity({"label": "Tag"})
        assert match_attribute(e, "label", ["tag"]) is False

    def test_case_match(self) -> None:
        """exact case match -> True"""
        e = _entity({"label": "Tag"})
        assert match_attribute(e, "label", ["Tag"]) is True
