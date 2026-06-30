"""Attribute value form-validation.

Enforces that an attribute value is either a scalar or a flat list of scalars.
"""

import re

Scalar = str | int | float | bool

_ID_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]*$")


class FormError(ValueError):
    """Raised when an attribute value has a malformed shape."""


def validate_attribute_value(value: object) -> None:
    """Validate that *value* is a Scalar or a flat list of Scalars.

    Raises ``FormError`` if the value has any other shape.
    """
    if isinstance(value, (str, int, float, bool)):
        return None
    if isinstance(value, list):
        for i, item in enumerate(value):
            if not isinstance(item, (str, int, float, bool)):
                raise FormError(f"list element {i} is {type(item).__name__}, expected a scalar")
        return None
    raise FormError(f"expected a scalar or list of scalars, got {type(value).__name__}")


def validate_id(value: str) -> None:
    """Validate that *value* is a filesystem-safe entity id.

    Raises ``FormError`` if *value* is empty, too long (> 200 chars),
    or contains characters outside ``[A-Za-z0-9._-]`` (first char may
    not be a dot).
    """
    if not value or len(value) > 200 or not _ID_RE.match(value):
        raise FormError(f"invalid id: {value!r}")
    return None
