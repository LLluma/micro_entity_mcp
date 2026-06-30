"""Tests for attribute value form-validation."""

import pytest

from micro_entity.validation import (
    FormError,
    Scalar,
    validate_against_set,
    validate_attribute_value,
    validate_id,
)


class TestScalarsPass:
    """Scalar values (str, int, float, bool) must pass validation."""

    @pytest.mark.parametrize(
        "value",
        ["x", "", 0, 3.14, True, False, -1, 42],
        ids=["str", "empty_str", "zero", "float", "true", "false", "neg_int", "int"],
    )
    def test_scalar_passes(self, value: object) -> None:
        assert validate_attribute_value(value) is None


class TestFlatListPasses:
    """A flat list of scalars must pass validation."""

    @pytest.mark.parametrize(
        "value",
        [["a", "b"], [1, 2], [], [1, "mixed", 3.14, True]],
        ids=["strings", "ints", "empty", "mixed_scalars"],
    )
    def test_flat_list_passes(self, value: object) -> None:
        assert validate_attribute_value(value) is None


class TestMalformedValuesRaise:
    """Non-scalar, non-flat-list values must raise FormError."""

    @pytest.mark.parametrize(
        "value",
        [
            {"key": "val"},
            [["nested"]],
            [{"inside": 1}],
            None,
            (1, 2),
            {1, 2},
        ],
        ids=["dict", "nested_list", "list_of_dict", "none", "tuple", "set"],
    )
    def test_malformed_raises_form_error(self, value: object) -> None:
        with pytest.raises(FormError):
            validate_attribute_value(value)


class TestFormErrorIsValueError:
    """FormError must be a ValueError subclass."""

    def test_form_error_is_value_error(self) -> None:
        assert issubclass(FormError, ValueError)

    def test_form_error_caught_as_value_error(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_value(None)


class TestScalarAlias:
    """The Scalar type alias must be importable and match the spec."""

    def test_scalar_alias_is_exported(self) -> None:
        # Scalar = str | int | float | bool — it's a UnionType
        assert Scalar is not None


class TestValidIdPasses:
    """Valid IDs must pass validate_id without error."""

    @pytest.mark.parametrize(
        "value",
        ["ADR-0007", "001", "build-entity", "3f9a_b2"],
        ids=["adr", "numeric", "kebab", "mixed"],
    )
    def test_valid_id_passes(self, value: str) -> None:
        assert validate_id(value) is None


class TestInvalidIdRaises:
    """Invalid IDs must raise FormError."""

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "hello world",
            "path/sep",
            "back\\slash",
            ".",
            "..",
            ".hidden",
            "\N{SNOWMAN}",
            "\x00bad",
            "a" * 201,
        ],
        ids=[
            "empty",
            "whitespace",
            "fwd_slash",
            "backslash",
            "dot",
            "dotdot",
            "leading_dot",
            "non_ascii",
            "control_char",
            "too_long",
        ],
    )
    def test_invalid_id_raises(self, value: str) -> None:
        with pytest.raises(FormError):
            validate_id(value)


class TestValidateAgainstSet:
    """Tests for validate_against_set — type-strict membership in an allowed set."""

    def test_scalar_present_in_allowed_passes(self) -> None:
        """A scalar value present in the allowed set passes (no exception)."""
        allowed = {"red", "green", "blue"}
        assert validate_against_set("green", allowed) is None

    def test_scalar_absent_raises_form_error(self) -> None:
        """A scalar absent from the allowed set raises FormError."""
        allowed = {"red", "green", "blue"}
        with pytest.raises(FormError):
            validate_against_set("yellow", allowed)

    def test_list_all_elements_in_set_passes(self) -> None:
        """A list whose every element is in the set passes."""
        allowed = {"red", "green", "blue"}
        assert validate_against_set(["red", "blue"], allowed) is None

    def test_list_one_element_absent_raises(self) -> None:
        """A list with one element absent raises FormError naming that element."""
        allowed = {"red", "green", "blue"}
        with pytest.raises(FormError):
            validate_against_set(["red", "yellow"], allowed)

    def test_empty_list_value_passes(self) -> None:
        """An empty list value passes (vacuously true)."""
        allowed = {"red", "green", "blue"}
        assert validate_against_set([], allowed) is None

    def test_empty_allowed_set_scalar_raises(self) -> None:
        """Empty allowed set with a scalar raises FormError."""
        with pytest.raises(FormError):
            validate_against_set("red", set())

    def test_empty_allowed_set_nonempty_list_raises(self) -> None:
        """Empty allowed set with a non-empty list raises FormError."""
        with pytest.raises(FormError):
            validate_against_set(["red"], set())

    def test_empty_allowed_set_empty_list_passes(self) -> None:
        """Empty allowed set with an empty list passes."""
        assert validate_against_set([], set()) is None

    def test_type_strict_int_not_in_str_set(self) -> None:
        """Type-strict check: 1 (int) not in {"1"} (str set) raises FormError."""
        allowed: set[str] = {"1"}
        with pytest.raises(FormError):
            validate_against_set(1, allowed)

    def test_error_message_includes_offending_and_allowed(self) -> None:
        """The error message includes the offending value and the allowed set."""
        allowed = {"red", "green", "blue"}
        try:
            validate_against_set("yellow", allowed)
            raise AssertionError("should have raised FormError")
        except FormError as exc:
            msg = str(exc)
            assert "yellow" in msg
            assert "red" in msg
            assert "green" in msg
            assert "blue" in msg
