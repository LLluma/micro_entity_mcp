"""Attribute matching against entities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

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


def query(entities: Iterable[Entity], criteria: Mapping[str, list[Scalar]]) -> list[Entity]:
    """Return entities matching every (key, values) pair in *criteria*.

    Logical AND across keys, OR across values within a key (delegated to
    :func:`match_attribute`).  Empty *criteria* matches all (vacuous AND).
    """
    if not criteria:
        return list(entities)

    return [e for e in entities if all(match_attribute(e, k, vs) for k, vs in criteria.items())]


def entity_matches_text(entity: Entity, needle: str) -> bool:
    """Return True when needle appears in body or any attribute value.

    Matching is case-insensitive. List-valued attributes match if any element
    contains needle after stringification.
    """
    low = needle.lower()
    if entity.body is not None and low in entity.body.lower():
        return True
    for value in entity.attributes.values():
        if isinstance(value, list):
            for v in value:
                if low in str(v).lower():
                    return True
        else:
            if low in str(value).lower():
                return True
    return False
