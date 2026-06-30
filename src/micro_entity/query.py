"""Attribute matching against entities."""

from __future__ import annotations

from micro_entity.entity import Entity
from micro_entity.validation import Scalar


def _strict_equal(a: object, b: object) -> bool:
    """Type-strict equality: type(a) is type(b) and a == b."""
    return type(a) is type(b) and a == b


def match_attribute(entity: Entity, key: str, values: list[Scalar]) -> bool:
    """Return True iff *entity* has *key* and its value intersects *values*.

    Intersection uses type-strict equality (no 1==1.0 collapse, no bool/int
    equivalence).  Empty *values* always returns False.
    """
    if not values:
        return False

    attr_raw = entity.attributes.get(key)
    if attr_raw is None:
        return False

    # Normalize: scalar -> [scalar]; list stays.
    if isinstance(attr_raw, list):
        attr_items: list[Scalar] = attr_raw
    else:
        attr_items = [attr_raw]

    for a in attr_items:
        for v in values:
            if _strict_equal(a, v):
                return True

    return False
