"""Tests for match_attribute in micro_entity/query.py."""

from datetime import UTC, datetime

from micro_entity.entity import Entity
from micro_entity.query import entity_matches_text, match_attribute, query
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


# --- query: multi-attribute filtering ---


def _entities(attrs_list: list[dict[str, Scalar | list[Scalar]]]) -> list[Entity]:
    ts = _fixture_ts
    return [
        Entity(id=f"e{i}", created=ts, updated=ts, attributes=a) for i, a in enumerate(attrs_list)
    ]


# --- text matching ---


class TestEntityMatchesText:
    def test_body_substring_case_insensitive(self) -> None:
        e = Entity(
            id="e1",
            created=_fixture_ts,
            updated=_fixture_ts,
            body="Hello World",
            attributes={"x": "y"},
        )
        assert entity_matches_text(e, "world") is True

    def test_scalar_attribute_value_matches(self) -> None:
        e = _entity({"status": "Done"})
        assert entity_matches_text(e, "done") is True

    def test_list_attribute_element_matches(self) -> None:
        e = _entity({"tags": ["alpha", "beta"]})
        assert entity_matches_text(e, "BETA") is True

    def test_missing_text_returns_false(self) -> None:
        e = _entity({"status": "open"})
        assert entity_matches_text(e, "closed") is False

    def test_none_body_does_not_match(self) -> None:
        e = _entity({"status": "open"})
        assert entity_matches_text(e, "body") is False


class TestQueryTwoCriteria:
    def test_and_must_both_match(self) -> None:
        """two criteria -> only entities matching BOTH"""
        es = _entities(
            [
                {"color": "red", "size": "small"},  # matches both
                {"color": "red", "size": "large"},  # matches only color
                {"color": "blue", "size": "small"},  # matches only size
                {"color": "blue", "size": "large"},  # matches neither
            ]
        )
        result = query(es, {"color": ["red"], "size": ["small"]})
        assert len(result) == 1
        assert result[0].attributes == {"color": "red", "size": "small"}

    def test_entity_matching_one_but_not_other_excluded(self) -> None:
        """entity matching one criterion but not other -> excluded"""
        es = _entities([{"color": "red", "size": "large"}])
        result = query(es, {"color": ["red"], "size": ["small"]})
        assert result == []


class TestQueryValuesOr:
    def test_single_criterion_or(self) -> None:
        """within a single criterion the values OR — matches any"""
        es = _entities(
            [
                {"color": "red"},
                {"color": "blue"},
                {"color": "green"},
            ]
        )
        result = query(es, {"color": ["red", "green"]})
        assert len(result) == 2
        assert result[0].attributes == {"color": "red"}
        assert result[1].attributes == {"color": "green"}


class TestQueryEmptyCriteria:
    def test_empty_criteria_returns_all(self) -> None:
        """criteria == {} -> return ALL entities, same objects, same order"""
        es = _entities([{"x": "a"}, {"x": "b"}, {"x": "c"}])
        result = query(es, {})
        assert len(result) == 3
        assert all(result[i] is es[i] for i in range(len(es)))

    def test_empty_entities_with_criteria(self) -> None:
        """query([], {...}) -> []"""
        result = query([], {"color": ["red"]})
        assert result == []


class TestQueryEmptyValues:
    def test_empty_value_list_excludes_all(self) -> None:
        """one criterion with [] -> no entity matches, even if other would"""
        es = _entities([{"color": "red", "size": "small"}])
        result = query(es, {"color": ["red"], "size": []})
        assert result == []


class TestQueryStable:
    def test_result_order_equals_input_order(self) -> None:
        """stable filter — result order matches input order"""
        es = _entities([{"val": i} for i in range(6)])
        # criteria match x0, x2, x4, x5 (values 0,2,4,5)
        result = query(es, {"val": [0, 2, 4, 5]})
        assert [e.id for e in result] == ["e0", "e2", "e4", "e5"]
