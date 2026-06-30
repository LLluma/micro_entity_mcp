"""Tests for attribute value form-validation."""

import pytest

from micro_entity.validation import FormError, Scalar, validate_attribute_value


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
